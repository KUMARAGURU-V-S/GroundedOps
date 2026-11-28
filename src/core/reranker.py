"""
Reranking & Diversity Filtering for GroundedOps.
Provides:
  1. Reciprocal Rank Fusion (RRF) to merge dense S3 vectors with BM25 lexical scores.
  2. Maximal Marginal Relevance (MMR) to maximize coverage while suppressing duplicate chunks.
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from .vector_store import SearchResult


def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[SearchResult, float]]],
    weights: Optional[List[float]] = None,
    rrf_k: int = 60,
    top_k: int = 4,
) -> List[SearchResult]:
    """
    Fuse multiple ranked result sets using Reciprocal Rank Fusion (RRF).
    Formula: score(d) = sum( weight_m / (k + rank_m(d)) )
    """
    if not ranked_lists:
        return []

    if weights is None:
        weights = [1.0] * len(ranked_lists)

    scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    for list_idx, ranked_list in enumerate(ranked_lists):
        w = weights[list_idx]
        for rank, (item, _raw_score) in enumerate(ranked_list, start=1):
            chunk_id = item.chunk_id
            chunk_map[chunk_id] = item
            rrf_score = w / (rrf_k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_score

    # Sort chunks descending by fused RRF score
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    fused_results: List[SearchResult] = []
    for chunk_id, fused_score in sorted_items[:top_k]:
        original = chunk_map[chunk_id]
        fused_results.append(
            SearchResult(
                chunk_id=original.chunk_id,
                doc_id=original.doc_id,
                doc_title=original.doc_title,
                section=original.section,
                content=original.content,
                score=round(fused_score, 4),
                metadata={**original.metadata, "retrieval_method": "hybrid_rrf"},
            )
        )

    return fused_results


def maximal_marginal_relevance(
    query_vector: List[float],
    candidate_chunks: List[SearchResult],
    candidate_vectors: List[List[float]],
    lambda_param: float = 0.7,
    top_k: int = 4,
) -> List[SearchResult]:
    """
    Maximal Marginal Relevance (MMR) reranking.
    Balances relevance to query with novelty compared to already selected chunks.
    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity. Default 0.7.
    """
    if not candidate_chunks:
        return []

    if len(candidate_chunks) <= top_k:
        return candidate_chunks

    def cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    selected_indices: List[int] = []
    unselected_indices: List[int] = list(range(len(candidate_chunks)))

    # Compute similarity between query and all candidate chunks
    query_sims = [cosine_sim(query_vector, vec) for vec in candidate_vectors]

    # Select the first chunk with highest query similarity
    best_first = max(unselected_indices, key=lambda idx: query_sims[idx])
    selected_indices.append(best_first)
    unselected_indices.remove(best_first)

    # Iteratively select remaining chunks using MMR formula
    while len(selected_indices) < top_k and unselected_indices:
        mmr_scores: List[Tuple[float, int]] = []
        for idx in unselected_indices:
            sim_to_query = query_sims[idx]
            max_sim_to_selected = max(
                cosine_sim(candidate_vectors[idx], candidate_vectors[sel_idx])
                for sel_idx in selected_indices
            )
            score = (lambda_param * sim_to_query) - ((1.0 - lambda_param) * max_sim_to_selected)
            mmr_scores.append((score, idx))

        best_next = max(mmr_scores, key=lambda x: x[0])[1]
        selected_indices.append(best_next)
        unselected_indices.remove(best_next)

    return [candidate_chunks[i] for i in selected_indices]
