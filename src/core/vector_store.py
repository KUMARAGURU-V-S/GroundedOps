"""
S3 Vectors Store for GroundedOps.
Serverless vector storage and similarity search engine native to Amazon S3.
Stores document chunks, metadata, and high-dimensional embeddings directly in S3,
eliminating dedicated vector database hosting costs (OpenSearch/Pinecone) while
delivering sub-second similarity search via AWS Lambda.
Supports both AWS S3 object storage and local filesystem emulation for offline development.
"""

import json
import math
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from .chunker import DocumentChunk
from ..utils.logger import get_logger

logger = get_logger("groundedops.vector_store")


@dataclass
class SearchResult:
    """Represents a retrieved document chunk with similarity score."""

    chunk_id: str
    doc_id: str
    doc_title: str
    section: str
    content: str
    score: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class S3VectorStore:
    """
    Serverless Vector Store backed by Amazon S3.

    S3 Layout:
      s3://{bucket}/{prefix}/catalog.json               <- Global index catalog & metadata
      s3://{bucket}/{prefix}/docs/{doc_id}/chunks.json   <- Chunks, embeddings & metadata for doc
      s3://{bucket}/{prefix}/index/all_vectors.json     <- Consolidated search index
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: str = "vectors",
        region_name: Optional[str] = None,
        s3_client: Optional[Any] = None,
        local_dir: Optional[str] = None,
    ):
        self.bucket_name = (
            bucket_name
            or os.environ.get("VECTORS_BUCKET_NAME")
            or os.environ.get("S3_VECTORS_BUCKET")
            or "groundedops-vectors"
        )
        self.prefix = prefix.strip("/")
        self.region_name = (
            region_name
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.local_mode = (
            os.environ.get("LOCAL_VECTOR_STORE", "false").lower() == "true"
            or os.environ.get("MOCK_S3", "false").lower() == "true"
        )
        self.local_dir = local_dir or os.environ.get("LOCAL_STORAGE_DIR", ".local_s3_vectors")

        if s3_client:
            self.s3 = s3_client
            self.use_boto = True
        elif self.local_mode:
            self.s3 = None
            self.use_boto = False
        else:
            try:
                config = Config(
                    region_name=self.region_name,
                    retries={"max_attempts": 3, "mode": "standard"},
                )
                self.s3 = boto3.client("s3", config=config)
                self.use_boto = True
            except Exception as e:
                logger.warning(f"Could not initialize S3 client: {e}. Falling back to local storage.")
                self.s3 = None
                self.use_boto = False

    def _catalog_key(self) -> str:
        return f"{self.prefix}/catalog.json"

    def _doc_key(self, doc_id: str) -> str:
        safe_id = doc_id.replace("/", "_").replace(" ", "_")
        return f"{self.prefix}/docs/{safe_id}/chunks.json"

    def _combined_index_key(self) -> str:
        return f"{self.prefix}/index/all_vectors.json"

    def _write_object(self, key: str, data_str: str) -> None:
        """Write object to S3 or local storage fallback."""
        if self.use_boto and self.s3:
            try:
                self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data_str.encode("utf-8"),
                    ContentType="application/json",
                )
                return
            except (ClientError, NoCredentialsError) as e:
                # If bucket doesn't exist or no AWS credentials, fallback to local storage
                logger.info(f"S3 put failed ({e}). Storing in local vector cache: {self.local_dir}")
                self.use_boto = False

        # Local storage fallback
        path = os.path.join(self.local_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data_str)

    def _read_object(self, key: str) -> Optional[str]:
        """Read object from S3 or local storage fallback."""
        if self.use_boto and self.s3:
            try:
                resp = self.s3.get_object(Bucket=self.bucket_name, Key=key)
                return resp["Body"].read().decode("utf-8")
            except ClientError as e:
                if e.response["Error"]["Code"] in ["NoSuchKey", "404"]:
                    return None
                # Other S3 error (e.g. bucket doesn't exist)
                self.use_boto = False
            except NoCredentialsError:
                self.use_boto = False

        path = os.path.join(self.local_dir, key)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _delete_object(self, key: str) -> bool:
        """Delete object from S3 or local storage fallback."""
        if self.use_boto and self.s3:
            try:
                self.s3.delete_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception:
                pass

        path = os.path.join(self.local_dir, key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec_a) != len(vec_b):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def save_document_vectors(
        self,
        doc_id: str,
        doc_title: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> Dict[str, Any]:
        """
        Save chunks and their embeddings for a document to S3 Vectors.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        records = []
        for chunk, emb in zip(chunks, embeddings):
            record = {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "doc_title": chunk.doc_title,
                "section": chunk.section,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "token_count_est": chunk.token_count_est,
                "content_hash": chunk.content_hash,
                "metadata": chunk.metadata,
                "embedding": emb,
            }
            records.append(record)

        doc_key = self._doc_key(doc_id)
        self._write_object(doc_key, json.dumps(records))

        self._update_catalog_and_index(doc_id, doc_title, len(records), records)

        logger.info(
            f"Successfully stored {len(records)} vectors for doc '{doc_id}' in s3://{self.bucket_name}/{doc_key}"
        )
        return {
            "doc_id": doc_id,
            "chunks_stored": len(records),
            "s3_key": doc_key,
        }

    def _get_catalog(self) -> Dict[str, Any]:
        """Fetch index catalog."""
        content = self._read_object(self._catalog_key())
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return {"documents": {}, "total_chunks": 0, "last_updated": 0}

    def _update_catalog_and_index(
        self,
        doc_id: str,
        doc_title: str,
        chunk_count: int,
        records: List[Dict[str, Any]],
    ) -> None:
        """Refresh index catalog and rebuild search partition."""
        catalog = self._get_catalog()
        catalog["documents"][doc_id] = {
            "title": doc_title,
            "chunk_count": chunk_count,
            "key": self._doc_key(doc_id),
            "updated_at": int(time.time()),
        }
        catalog["total_chunks"] = sum(
            d["chunk_count"] for d in catalog["documents"].values()
        )
        catalog["last_updated"] = int(time.time())

        self._write_object(self._catalog_key(), json.dumps(catalog))
        self._rebuild_consolidated_index(catalog)

    def _rebuild_consolidated_index(self, catalog: Dict[str, Any]) -> None:
        """Consolidates all document vectors into a unified search index."""
        all_records = []
        for doc_id, meta in catalog.get("documents", {}).items():
            content = self._read_object(meta["key"])
            if content:
                try:
                    all_records.extend(json.loads(content))
                except Exception as e:
                    logger.warning(f"Could not load records for {doc_id}: {e}")

        self._write_object(self._combined_index_key(), json.dumps(all_records))

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 4,
        min_score: float = 0.10,
        filter_doc_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Execute vector similarity search across indexed S3 chunks.
        Loads index partition, computes cosine similarity, and ranks top-k chunks.
        """
        records = []
        if filter_doc_id:
            content = self._read_object(self._doc_key(filter_doc_id))
            if content:
                records = json.loads(content)
        else:
            content = self._read_object(self._combined_index_key())
            if content:
                records = json.loads(content)
            else:
                catalog = self._get_catalog()
                for meta in catalog.get("documents", {}).values():
                    d_content = self._read_object(meta["key"])
                    if d_content:
                        records.extend(json.loads(d_content))

        if not records:
            return []

        scored_results: List[Tuple[float, Dict[str, Any]]] = []
        for r in records:
            emb = r.get("embedding", [])
            score = self._cosine_similarity(query_vector, emb)
            if score >= min_score:
                scored_results.append((score, r))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        results: List[SearchResult] = []
        for score, r in scored_results[:top_k]:
            results.append(
                SearchResult(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r.get("doc_title", r["doc_id"]),
                    section=r.get("section", "General"),
                    content=r["content"],
                    score=round(score, 4),
                    metadata=r.get("metadata", {}),
                )
            )

        return results

    def hybrid_search(
        self,
        query: str,
        query_vector: List[float],
        top_k: int = 4,
        alpha: float = 0.5,
        min_score: float = 0.05,
        filter_doc_id: Optional[str] = None,
        use_mmr: bool = False,
    ) -> List[SearchResult]:
        """
        Execute Hybrid Search combining Dense S3 Vectors with BM25 Lexical Keyword search
        via Reciprocal Rank Fusion (RRF).
        alpha: Weight given to dense vectors (1.0 = pure vector, 0.0 = pure BM25).
        """
        from .bm25 import BM25Okapi
        from .reranker import reciprocal_rank_fusion, maximal_marginal_relevance

        records = []
        if filter_doc_id:
            content = self._read_object(self._doc_key(filter_doc_id))
            if content:
                records = json.loads(content)
        else:
            content = self._read_object(self._combined_index_key())
            if content:
                records = json.loads(content)
            else:
                catalog = self._get_catalog()
                for meta in catalog.get("documents", {}).values():
                    d_content = self._read_object(meta["key"])
                    if d_content:
                        records.extend(json.loads(d_content))

        if not records:
            return []

        # 1. Dense Vector Scoring (filter by min_score)
        dense_ranked: List[Tuple[SearchResult, float]] = []
        for r in records:
            emb = r.get("embedding", [])
            score = self._cosine_similarity(query_vector, emb)
            if score >= min_score:
                sr = SearchResult(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r.get("doc_title", r["doc_id"]),
                    section=r.get("section", "General"),
                    content=r["content"],
                    score=round(score, 4),
                    metadata=r.get("metadata", {}),
                )
                dense_ranked.append((sr, score))

        dense_ranked.sort(key=lambda x: x[1], reverse=True)

        # 2. BM25 Sparse Lexical Scoring (filter non-zero matches)
        bm25 = BM25Okapi()
        corpus_texts = [f"{r.get('doc_title', '')} {r.get('section', '')}\n{r.get('content', '')}" for r in records]
        bm25.fit(corpus_texts)
        bm25_scores = bm25.score(query)

        bm25_ranked: List[Tuple[SearchResult, float]] = []
        for r, score in zip(records, bm25_scores):
            if score > 0.0:
                sr = SearchResult(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r.get("doc_title", r["doc_id"]),
                    section=r.get("section", "General"),
                    content=r["content"],
                    score=round(score, 4),
                    metadata=r.get("metadata", {}),
                )
                bm25_ranked.append((sr, score))

        bm25_ranked.sort(key=lambda x: x[1], reverse=True)

        max_bm25 = max(bm25_scores) if bm25_scores else 0.0
        # If no keywords matched in BM25 and dense similarity is below threshold, treat as out of domain
        if max_bm25 == 0.0 and (not dense_ranked or dense_ranked[0][1] < 0.15):
            return []

        if not dense_ranked and not bm25_ranked:
            return []

        # 3. Reciprocal Rank Fusion (RRF)
        fused = reciprocal_rank_fusion(
            ranked_lists=[dense_ranked, bm25_ranked],
            weights=[alpha, 1.0 - alpha],
            top_k=top_k * 2 if use_mmr else top_k,
        )

        # 4. Optional Maximal Marginal Relevance (MMR) for diversity
        if use_mmr and len(fused) > top_k:
            candidate_vectors = [
                next((r.get("embedding", []) for r in records if r["chunk_id"] == c.chunk_id), [])
                for c in fused
            ]
            fused = maximal_marginal_relevance(
                query_vector=query_vector,
                candidate_chunks=fused,
                candidate_vectors=candidate_vectors,
                top_k=top_k,
            )

        return fused[:top_k]

    def list_indexed_documents(self) -> List[Dict[str, Any]]:
        """Return list of all documents currently indexed in S3 Vectors."""
        catalog = self._get_catalog()
        docs = []
        for doc_id, meta in catalog.get("documents", {}).items():
            docs.append(
                {
                    "doc_id": doc_id,
                    "title": meta.get("title", doc_id),
                    "chunk_count": meta.get("chunk_count", 0),
                    "updated_at": meta.get("updated_at", 0),
                }
            )
        return docs

    def delete_document(self, doc_id: str) -> bool:
        """Remove a document and its vectors from the S3 store."""
        doc_key = self._doc_key(doc_id)
        self._delete_object(doc_key)

        catalog = self._get_catalog()
        if doc_id in catalog.get("documents", {}):
            del catalog["documents"][doc_id]
            catalog["total_chunks"] = sum(
                d["chunk_count"] for d in catalog["documents"].values()
            )
            catalog["last_updated"] = int(time.time())
            self._write_object(self._catalog_key(), json.dumps(catalog))
            self._rebuild_consolidated_index(catalog)
            return True
        return False
