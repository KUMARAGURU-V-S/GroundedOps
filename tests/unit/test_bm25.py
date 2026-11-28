"""Unit tests for Okapi BM25 lexical search."""

from src.core.bm25 import BM25Okapi


def test_bm25_exact_keyword_matching():
    corpus = [
        "Aurora PostgreSQL cluster primary failover procedure and PgBouncer reload.",
        "Kubernetes worker node draining and OOMKilled exit code 137 pod remediation.",
        "Amazon Cognito authentication token expiry and group authorization hierarchy.",
    ]
    bm25 = BM25Okapi()
    bm25.fit(corpus)

    # Query for exact Kubernetes incident terms
    scores_k8s = bm25.score("OOMKilled exit code 137")
    assert scores_k8s[1] > scores_k8s[0]
    assert scores_k8s[1] > scores_k8s[2]

    # Query for database terms
    scores_db = bm25.score("Aurora PostgreSQL failover")
    assert scores_db[0] > scores_db[1]
    assert scores_db[0] > scores_db[2]


def test_bm25_empty_corpus():
    bm25 = BM25Okapi()
    bm25.fit([])
    scores = bm25.score("test query")
    assert scores == []
