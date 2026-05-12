import pytest
import re
from typing import List

def _bm25_score(query: str, documents: List[str]) -> List[float]:
    """Standalone BM25 scoring (mirrors RetrievalAgent._bm25_score)"""
    query_terms = query.lower().split()
    doc_lengths = [len(d.lower().split()) for d in documents]
    avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
    scores = []
    for doc in documents:
        doc_lower = doc.lower()
        doc_terms = doc_lower.split()
        doc_len = len(doc_terms)
        # Count term occurrences (word-boundary aware via regex)
        tf = sum(1 for term in query_terms for _ in re.findall(r'\b' + re.escape(term) + r'\b', doc_lower))
        k1 = 1.5
        b = 0.75
        doc_len_norm = doc_len / avg_dl if avg_dl > 0 else 1
        score = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len_norm)) if tf > 0 else 0.0
        scores.append(score)
    return scores

class TestBM25Scoring:
    def test_bm25_scores_vary_by_length(self):
        """BM25 scores vary based on term frequency AND document length"""
        docs = [
            "chunk chunk chunk word word test",  # 6 terms, 2 chunk matches
            "chunk word test document",           # 4 terms, 1 chunk match
            "word word word test",                 # 4 terms, 0 chunk matches
        ]
        scores = _bm25_score("chunk size", docs)
        # Scores must be distinct (vary by document)
        assert scores[0] != scores[1] != scores[2], f"All scores should differ: {scores}"
        # More term matches should yield higher raw tf
        assert scores[0] > scores[1]  # doc1 has 2 chunk matches, doc2 has 1

    def test_bm25_empty_query(self):
        """Empty query should not crash"""
        docs = ["test document content"]
        scores = _bm25_score("", docs)
        assert len(scores) == 1
        # Empty query = no terms to match = 0 score
        assert scores[0] == 0.0

    def test_bm25_same_length_varies_by_tf(self):
        """Same-length docs: more term matches = higher score"""
        docs = [
            "chunk chunk chunk chunk",  # 4 terms, 4 chunk matches (tf=4)
            "chunk chunk word word",    # 4 terms, 2 chunk matches (tf=2)
            "word word word word",      # 4 terms, 0 chunk matches (tf=0)
        ]
        scores = _bm25_score("chunk", docs)
        # Same length → length norm identical → ordering by tf only
        assert scores[0] > scores[1]  # tf=4 > tf=2
        assert scores[1] > scores[2]  # tf=2 > tf=0
        assert scores[0] != scores[1] != scores[2]