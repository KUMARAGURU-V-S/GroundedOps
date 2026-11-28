"""Unit tests for RAGPipeline."""

from src.core.chunker import MarkdownChunker
from src.core.embeddings import BedrockEmbeddings
from src.core.nova_client import AmazonNovaClient
from src.core.rag_pipeline import RAGPipeline
from src.core.vector_store import S3VectorStore


def test_rag_pipeline_end_to_end(mock_s3_bucket, sample_markdown):
    s3_client, bucket_name = mock_s3_bucket

    vector_store = S3VectorStore(bucket_name=bucket_name, s3_client=s3_client)
    embeddings = BedrockEmbeddings(dimensions=128, mock_mode=True)
    nova = AmazonNovaClient(mock_mode=True)
    chunker = MarkdownChunker()

    pipeline = RAGPipeline(
        vector_store=vector_store,
        embeddings=embeddings,
        nova_client=nova,
        chunker=chunker,
    )

    # 1. Ingest
    ingest_res = pipeline.ingest_document(
        doc_id="dr_guide.md",
        content=sample_markdown,
        metadata={"author": "SRE"},
    )
    assert ingest_res["chunks_count"] > 0

    # 2. Dense Query
    query_res = pipeline.query("How to failover primary database?", search_mode="dense")
    assert query_res["is_grounded"] is True
    assert len(query_res["citations"]) > 0
    assert query_res["metrics"]["total_latency_ms"] > 0

    # 3. Hybrid Search Query (BM25 + S3 Vectors RRF)
    hybrid_res = pipeline.query("How to failover primary database?", search_mode="hybrid", use_mmr=True)
    assert hybrid_res["is_grounded"] is True
    assert hybrid_res["metrics"]["search_mode"] == "hybrid"

    # 4. Multi-turn Conversational Memory
    history = [
        {"role": "user", "content": "What is the RPO?"},
        {"role": "assistant", "content": "The recovery point objective is 5 minutes."},
    ]
    chat_res = pipeline.query("What about failover steps?", chat_history=history)
    assert chat_res["is_grounded"] is True

    # 5. Stats
    stats = pipeline.get_pipeline_stats()
    assert stats["indexed_documents_count"] == 1
    assert stats["total_chunks_count"] == ingest_res["chunks_count"]
