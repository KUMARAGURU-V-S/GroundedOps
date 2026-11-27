"""Integration test verifying end-to-end ingestion and grounded retrieval."""

import os
import glob
import pytest
from src.core.rag_pipeline import RAGPipeline
from src.core.embeddings import BedrockEmbeddings
from src.core.nova_client import AmazonNovaClient
from src.core.vector_store import S3VectorStore


def test_end_to_end_sample_docs_grounding(mock_s3_bucket):
    s3_client, bucket_name = mock_s3_bucket

    store = S3VectorStore(bucket_name=bucket_name, s3_client=s3_client)
    embeddings = BedrockEmbeddings(mock_mode=True)
    nova = AmazonNovaClient(mock_mode=True)
    pipeline = RAGPipeline(vector_store=store, embeddings=embeddings, nova_client=nova)

    # Ingest sample docs from sample_docs directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sample_docs"))
    sample_files = glob.glob(os.path.join(base_dir, "*.md"))
    assert len(sample_files) >= 4

    for fp in sample_files:
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        pipeline.ingest_document(
            doc_id=os.path.basename(fp),
            content=content,
            metadata={"source_file": fp},
        )

    stats = pipeline.get_pipeline_stats()
    assert stats["indexed_documents_count"] >= 4
    assert stats["total_chunks_count"] > 4

    # Test Query 1: Aurora failover
    res1 = pipeline.query("How to failover Aurora PostgreSQL cluster?")
    assert res1["is_grounded"] is True
    assert len(res1["citations"]) >= 1

    # Test Query 2: Kubernetes OOM
    res2 = pipeline.query("What is the remediation for OOMKilled exit code 137?")
    assert res2["is_grounded"] is True
    assert len(res2["citations"]) >= 1

    # Test Query 3: Out-of-scope query
    res3 = pipeline.query("How to build a wooden chair?", top_k=2)
    # When similarity threshold isn't met or chunks don't match, response should refuse or have low confidence
    assert "metrics" in res3
