"""Unit tests for MarkdownChunker."""

from src.core.chunker import MarkdownChunker, DocumentChunk


def test_chunk_document_preserves_sections(sample_markdown):
    chunker = MarkdownChunker(chunk_size=400, chunk_overlap=50)
    chunks = chunker.chunk_document(doc_id="dr_plan.md", content=sample_markdown)

    assert len(chunks) >= 3
    assert all(isinstance(c, DocumentChunk) for c in chunks)
    assert chunks[0].doc_title == "Disaster Recovery Plan"

    sections = [c.section for c in chunks]
    assert "Overview" in sections
    assert "Database Failover" in sections
    assert "Escalation" in sections


def test_chunker_sliding_window_large_content():
    chunker = MarkdownChunker(chunk_size=200, chunk_overlap=40, min_chunk_size=50)
    large_text = "# Large Guide\n\n## Deep Dive\n" + ("This is detailed operational instruction. " * 30)

    chunks = chunker.chunk_document(doc_id="large.md", content=large_text)
    assert len(chunks) > 1

    # Verify chunk IDs and indices are sequential
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.chunk_id == f"large.md#c{i}"
        assert c.token_count_est > 0


def test_chunker_empty_content():
    chunker = MarkdownChunker()
    chunks = chunker.chunk_document(doc_id="empty.md", content="")
    assert len(chunks) == 0
