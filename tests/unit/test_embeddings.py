"""Unit tests for BedrockEmbeddings."""

import math
from src.core.embeddings import BedrockEmbeddings


def test_mock_embeddings_normalized():
    embeddings = BedrockEmbeddings(dimensions=512, normalize=True, mock_mode=True)
    vec = embeddings.embed_text("Sample DevOps query")

    assert len(vec) == 512
    # Verify unit length (L2 norm == 1.0)
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


def test_batch_embeddings():
    embeddings = BedrockEmbeddings(dimensions=256, mock_mode=True)
    texts = ["First document", "Second runbook", "Third specification"]
    vecs = embeddings.embed_batch(texts)

    assert len(vecs) == 3
    assert all(len(v) == 256 for v in vecs)


def test_empty_string_embedding():
    embeddings = BedrockEmbeddings(dimensions=128, mock_mode=True)
    vec = embeddings.embed_text("")
    assert vec == [0.0] * 128
