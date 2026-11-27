"""Unit tests for S3VectorStore using Moto S3."""

import pytest
from src.core.chunker import MarkdownChunker
from src.core.embeddings import BedrockEmbeddings
from src.core.vector_store import S3VectorStore


def test_save_and_retrieve_vectors(mock_s3_bucket, sample_markdown):
    s3_client, bucket_name = mock_s3_bucket

    store = S3VectorStore(bucket_name=bucket_name, s3_client=s3_client)
    chunker = MarkdownChunker()
    embeddings_svc = BedrockEmbeddings(dimensions=128, mock_mode=True)

    chunks = chunker.chunk_document("doc1.md", sample_markdown)
    vectors = embeddings_svc.embed_batch([c.content for c in chunks])

    res = store.save_document_vectors("doc1.md", "Disaster Recovery Plan", chunks, vectors)
    assert res["chunks_stored"] == len(chunks)

    # Query using nearest vector
    query_vec = embeddings_svc.embed_text("How to failover database")
    search_results = store.similarity_search(query_vec, top_k=2)

    assert len(search_results) > 0
    assert search_results[0].doc_id == "doc1.md"
    assert search_results[0].score > 0.0


def test_catalog_tracking_and_deletion(mock_s3_bucket, sample_markdown):
    s3_client, bucket_name = mock_s3_bucket

    store = S3VectorStore(bucket_name=bucket_name, s3_client=s3_client)
    chunker = MarkdownChunker()
    embeddings_svc = BedrockEmbeddings(dimensions=128, mock_mode=True)

    chunks = chunker.chunk_document("doc2.md", sample_markdown)
    vectors = embeddings_svc.embed_batch([c.content for c in chunks])

    store.save_document_vectors("doc2.md", "Test Doc 2", chunks, vectors)

    docs = store.list_indexed_documents()
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "doc2.md"

    deleted = store.delete_document("doc2.md")
    assert deleted is True

    docs_after = store.list_indexed_documents()
    assert len(docs_after) == 0
