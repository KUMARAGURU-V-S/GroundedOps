"""Unit tests for RRF and MMR reranking."""

from src.core.reranker import maximal_marginal_relevance, reciprocal_rank_fusion
from src.core.vector_store import SearchResult


def test_reciprocal_rank_fusion():
    c1 = SearchResult("c1", "doc1", "Title 1", "Sec 1", "Content 1", 0.9, {})
    c2 = SearchResult("c2", "doc2", "Title 2", "Sec 2", "Content 2", 0.8, {})
    c3 = SearchResult("c3", "doc3", "Title 3", "Sec 3", "Content 3", 0.7, {})

    # List 1 ranks: c1, c2
    list_dense = [(c1, 0.9), (c2, 0.8)]
    # List 2 ranks: c2, c3
    list_bm25 = [(c2, 10.5), (c3, 8.2)]

    fused = reciprocal_rank_fusion(
        ranked_lists=[list_dense, list_bm25],
        top_k=2,
    )

    assert len(fused) == 2
    # c2 appeared high on both lists, so its combined RRF score should be highest!
    assert fused[0].chunk_id == "c2"


def test_maximal_marginal_relevance():
    query_vec = [1.0, 0.0]
    # c1 is identical to query [1.0, 0.0]
    # c2 is an almost identical duplicate of c1 [1.0, 0.01]
    # c3 is orthogonal/diverse to c1 but has positive query relevance
    c1 = SearchResult("c1", "doc1", "T1", "S1", "Text 1", 1.0, {})
    c2 = SearchResult("c2", "doc2", "T2", "S2", "Text 2", 0.95, {})
    c3 = SearchResult("c3", "doc3", "T3", "S3", "Text 3", 0.6, {})

    candidates = [c1, c2, c3]
    candidate_vecs = [
        [1.0, 0.0],
        [0.99, 0.01],
        [0.7, 0.7],
    ]

    # With lambda_param = 0.2 (strong diversity preference), redundant c2 is penalized
    selected = maximal_marginal_relevance(
        query_vector=query_vec,
        candidate_chunks=candidates,
        candidate_vectors=candidate_vecs,
        lambda_param=0.2,
        top_k=2,
    )

    assert len(selected) == 2
    assert selected[0].chunk_id == "c1"
    # Strong diversity preference selects diverse c3 over redundant c2
    assert selected[1].chunk_id == "c3"
