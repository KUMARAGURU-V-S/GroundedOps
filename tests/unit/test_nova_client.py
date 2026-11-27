"""Unit tests for AmazonNovaClient."""

from src.core.nova_client import AmazonNovaClient
from src.core.vector_store import SearchResult


def test_nova_client_grounded_generation():
    client = AmazonNovaClient(model_id="amazon.nova-micro-v1:0", mock_mode=True)

    chunks = [
        SearchResult(
            chunk_id="test#c0",
            doc_id="test.md",
            doc_title="Incident SOP",
            section="Remediation",
            content="Restart the proxy service using systemctl restart proxy.",
            score=0.91,
            metadata={},
        )
    ]

    resp = client.generate_grounded_answer(
        query="How do I restart the proxy?", chunks=chunks
    )

    assert resp.is_grounded is True
    assert resp.confidence_score > 0.8
    assert len(resp.citations) >= 1
    assert "Incident SOP" in resp.answer
    assert resp.model_id == "amazon.nova-micro-v1:0"


def test_nova_client_no_chunks_refusal():
    client = AmazonNovaClient(mock_mode=True)
    resp = client.generate_grounded_answer(query="Unrelated question", chunks=[])

    assert resp.is_grounded is False
    assert "not contain sufficient information" in resp.answer
    assert len(resp.citations) == 0
