"""
End-to-End RAG Pipeline for GroundedOps.
Coordinates document ingestion, chunking, embedding generation, S3 Vector storage,
hybrid retrieval (BM25 + S3 Vectors) with RRF, MMR reranking,
and evidence-grounded response generation via Amazon Bedrock Amazon Nova.
"""

import time
from typing import Any, Dict, Iterator, List, Optional

from .chunker import MarkdownChunker
from .embeddings import BedrockEmbeddings
from .nova_client import AmazonNovaClient, GroundedResponse
from .vector_store import S3VectorStore, SearchResult
from ..utils.logger import Timer, get_logger
from ..utils.sanitizer import sanitize_text
from ..utils.telemetry import MetricsEmitter

logger = get_logger("groundedops.pipeline")


class RAGPipeline:
    """
    Unified GroundedOps Retrieval-Augmented Generation Pipeline with Hybrid Search
    and Conversational Memory.
    """

    def __init__(
        self,
        vector_store: Optional[S3VectorStore] = None,
        embeddings: Optional[BedrockEmbeddings] = None,
        nova_client: Optional[AmazonNovaClient] = None,
        chunker: Optional[MarkdownChunker] = None,
        telemetry: Optional[MetricsEmitter] = None,
        top_k: int = 4,
        similarity_threshold: float = 0.10,
        default_search_mode: str = "hybrid",
    ):
        self.vector_store = vector_store or S3VectorStore()
        self.embeddings = embeddings or BedrockEmbeddings()
        self.nova_client = nova_client or AmazonNovaClient()
        self.chunker = chunker or MarkdownChunker()
        self.telemetry = telemetry or MetricsEmitter()
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.default_search_mode = default_search_mode

    def ingest_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingests a document: chunks text, computes embeddings, and stores in S3 Vectors.
        Applies contextual prefixing (title + section) to each chunk to enhance retrieval accuracy.
        """
        metadata = metadata or {}
        logger.info(f"Starting ingestion for document: {doc_id}")

        with Timer("chunking") as chunk_timer:
            chunks = self.chunker.chunk_document(doc_id, content, metadata)

        if not chunks:
            raise ValueError(f"Document {doc_id} produced 0 chunks after processing.")

        doc_title = chunks[0].doc_title
        # Contextual chunk embedding: include document title & section header
        texts = [f"{c.doc_title} - {c.section}\n{c.content}" for c in chunks]

        with Timer("embedding") as emb_timer:
            vectors = self.embeddings.embed_batch(texts)

        with Timer("s3_storage") as s3_timer:
            result = self.vector_store.save_document_vectors(
                doc_id=doc_id,
                doc_title=doc_title,
                chunks=chunks,
                embeddings=vectors,
            )

        logger.info(
            f"Ingested '{doc_id}' into S3 Vectors: {len(chunks)} chunks "
            f"(chunk_time={chunk_timer.elapsed_ms:.1f}ms, "
            f"emb_time={emb_timer.elapsed_ms:.1f}ms, "
            f"s3_time={s3_timer.elapsed_ms:.1f}ms)"
        )

        return {
            "doc_id": doc_id,
            "title": doc_title,
            "chunks_count": len(chunks),
            "s3_key": result["s3_key"],
            "timing_ms": {
                "chunking": round(chunk_timer.elapsed_ms, 2),
                "embedding": round(emb_timer.elapsed_ms, 2),
                "storage": round(s3_timer.elapsed_ms, 2),
            },
        }

    def retrieve(
        self,
        question: str,
        top_k: Optional[int] = None,
        search_mode: Optional[str] = None,
        filter_doc_id: Optional[str] = None,
        use_mmr: bool = False,
    ) -> Tuple[List[SearchResult], float, float]:
        """
        Retrieval stage: embeds query and retrieves top-k chunks using Hybrid or Dense search.
        Returns: (chunks, embedding_latency_ms, retrieval_latency_ms)
        """
        k = top_k or self.top_k
        mode = search_mode or self.default_search_mode

        with Timer("query_embedding") as emb_timer:
            query_vector = self.embeddings.embed_text(question)

        with Timer("retrieval") as ret_timer:
            if mode == "hybrid":
                retrieved_chunks = self.vector_store.hybrid_search(
                    query=question,
                    query_vector=query_vector,
                    top_k=k,
                    alpha=0.5,
                    min_score=self.similarity_threshold,
                    filter_doc_id=filter_doc_id,
                    use_mmr=use_mmr,
                )
            else:
                retrieved_chunks = self.vector_store.similarity_search(
                    query_vector=query_vector,
                    top_k=k,
                    min_score=self.similarity_threshold,
                    filter_doc_id=filter_doc_id,
                )

        return retrieved_chunks, emb_timer.elapsed_ms, ret_timer.elapsed_ms

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        search_mode: Optional[str] = None,
        filter_doc_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        use_mmr: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a grounded query:
        1. Sanitizes question against secret/credential leakage.
        2. Retrieves candidate chunks (Hybrid BM25 + S3 Vectors or Dense).
        3. Invokes Amazon Nova to synthesize grounded answer with citations.
        4. Emits CloudWatch telemetry.
        """
        start_total = time.perf_counter()

        # Step 1: Security sanitization
        clean_question, redactions = sanitize_text(question)
        if redactions:
            logger.info(f"Redacted sensitive tokens in query: {redactions}")

        # Step 2: Retrieval
        retrieved_chunks, emb_time, ret_time = self.retrieve(
            question=clean_question,
            top_k=top_k,
            search_mode=search_mode,
            filter_doc_id=filter_doc_id,
            use_mmr=use_mmr,
        )

        # Step 3: Generation
        with Timer("nova_generation") as gen_timer:
            grounded_response: GroundedResponse = (
                self.nova_client.generate_grounded_answer(
                    query=clean_question,
                    chunks=retrieved_chunks,
                    chat_history=chat_history,
                )
            )

        total_latency = (time.perf_counter() - start_total) * 1000.0

        metrics = {
            "total_latency_ms": round(total_latency, 2),
            "embedding_latency_ms": round(emb_time, 2),
            "retrieval_latency_ms": round(ret_time, 2),
            "generation_latency_ms": round(gen_timer.elapsed_ms, 2),
            "retrieved_chunks_count": len(retrieved_chunks),
            "search_mode": search_mode or self.default_search_mode,
        }

        # Step 4: Telemetry emission
        self.telemetry.emit_query_metrics(
            metrics=metrics,
            is_grounded=grounded_response.is_grounded,
            confidence_score=grounded_response.confidence_score,
        )

        return {
            "question": clean_question,
            "answer": grounded_response.answer,
            "is_grounded": grounded_response.is_grounded,
            "confidence_score": grounded_response.confidence_score,
            "model_id": grounded_response.model_id,
            "citations": [c.to_dict() for c in grounded_response.citations],
            "retrieved_context": [c.to_dict() for c in retrieved_chunks],
            "metrics": metrics,
            "redactions": redactions,
        }

    def stream_query(
        self,
        question: str,
        top_k: Optional[int] = None,
        search_mode: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterator[str]:
        """Stream response tokens directly from Amazon Nova."""
        clean_question, _ = sanitize_text(question)
        chunks, _, _ = self.retrieve(
            question=clean_question,
            top_k=top_k,
            search_mode=search_mode,
        )
        return self.nova_client.stream_grounded_answer(
            query=clean_question,
            chunks=chunks,
            chat_history=chat_history,
        )

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Returns statistics about indexed documents and pipeline configuration."""
        docs = self.vector_store.list_indexed_documents()
        total_chunks = sum(d["chunk_count"] for d in docs)
        return {
            "status": "healthy",
            "vector_store_type": "Amazon S3 Vectors (Serverless)",
            "retrieval_engine": "Hybrid (BM25 + S3 Dense Vectors RRF)",
            "vector_bucket": self.vector_store.bucket_name,
            "embedding_model": self.embeddings.model_id,
            "generation_model": self.nova_client.model_id,
            "indexed_documents_count": len(docs),
            "total_chunks_count": total_chunks,
            "documents": docs,
        }
