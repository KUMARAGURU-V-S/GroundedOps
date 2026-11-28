"""
Okapi BM25 Lexical Search Engine for GroundedOps.
Provides keyword-based sparse retrieval to complement dense S3 vector embeddings,
ensuring high precision for operational terms (error codes, cluster identifiers, commands).
"""

import math
import re
from typing import Dict, List, Set, Tuple


class BM25Okapi:
    """
    Okapi BM25 scoring algorithm.
    Parameters:
      k1: Term frequency saturation parameter (typically 1.2 to 2.0).
      b: Document length normalization parameter (typically 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        """Normalize and tokenize text into lowercase alphanumeric words."""
        return re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())

    def fit(self, corpus_texts: List[str]) -> "BM25Okapi":
        """Index a corpus of document texts for BM25 scoring."""
        self.corpus_size = len(corpus_texts)
        if self.corpus_size == 0:
            self.avg_doc_len = 0.0
            return self

        total_tokens = 0
        self.doc_lengths = []
        self.doc_freqs = []
        df_counts: Dict[str, int] = {}

        for text in corpus_texts:
            tokens = self._tokenize(text)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_tokens += doc_len

            frequencies: Dict[str, int] = {}
            seen_in_doc: Set[str] = set()
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
                if token not in seen_in_doc:
                    df_counts[token] = df_counts.get(token, 0) + 1
                    seen_in_doc.add(token)

            self.doc_freqs.append(frequencies)

        self.avg_doc_len = total_tokens / self.corpus_size if self.corpus_size > 0 else 0.0

        # Compute IDF using Lucene/standard Okapi formula with smoothing
        self.idf = {}
        for term, df in df_counts.items():
            # ln((N - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[term] = math.log(((self.corpus_size - df + 0.5) / (df + 0.5)) + 1.0)

        return self

    def score(self, query: str) -> List[float]:
        """Compute BM25 relevance scores for all documents in the corpus for a given query."""
        if self.corpus_size == 0:
            return []

        query_tokens = self._tokenize(query)
        scores = [0.0] * self.corpus_size

        for term in query_tokens:
            if term not in self.idf:
                continue

            term_idf = self.idf[term]

            for i in range(self.corpus_size):
                doc_freq = self.doc_freqs[i].get(term, 0)
                if doc_freq == 0:
                    continue

                doc_len = self.doc_lengths[i]
                numerator = doc_freq * (self.k1 + 1.0)
                denominator = doc_freq + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                scores[i] += term_idf * (numerator / denominator)

        return scores
