"""
Hybrid Search Service for RAG
Combines semantic (vector) search with keyword (BM25) search
using Reciprocal Rank Fusion (RRF) for improved retrieval accuracy.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined score."""
    chunk_id: int
    content: str
    document_id: int
    document_name: str
    page_number: Optional[int]
    vector_score: float  # Semantic similarity (0-1)
    keyword_score: float  # BM25 score (normalized 0-1)
    combined_score: float  # RRF combined score
    vector_rank: int
    keyword_rank: int


class BM25:
    """
    Simple BM25 implementation for keyword scoring.
    BM25 is a bag-of-words ranking function used for information retrieval.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Args:
            k1: Term frequency saturation parameter (1.2-2.0 typical)
            b: Document length normalization (0-1, 0.75 typical)
        """
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.doc_freqs = defaultdict(int)  # Term -> number of docs containing term
        self.idf = {}
        self.doc_term_freqs = []  # List of {term: freq} for each doc
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, alphanumeric only."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        return tokens
    
    def fit(self, corpus: List[str]):
        """
        Build the BM25 index from a corpus of documents.
        
        Args:
            corpus: List of document strings
        """
        self.corpus = corpus
        n_docs = len(corpus)
        
        if n_docs == 0:
            return
        
        # Tokenize and compute statistics
        self.doc_term_freqs = []
        self.doc_lengths = []
        
        for doc in corpus:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            
            # Count term frequencies in this doc
            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1
            self.doc_term_freqs.append(dict(term_freq))
            
            # Update document frequencies
            for term in set(tokens):
                self.doc_freqs[term] += 1
        
        self.avg_doc_length = sum(self.doc_lengths) / n_docs if n_docs > 0 else 0
        
        # Compute IDF for each term
        import math
        for term, df in self.doc_freqs.items():
            # IDF formula: log((N - df + 0.5) / (df + 0.5) + 1)
            self.idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
    
    def get_scores(self, query: str) -> List[float]:
        """
        Compute BM25 scores for all documents given a query.
        
        Args:
            query: The search query string
            
        Returns:
            List of BM25 scores for each document
        """
        query_tokens = self._tokenize(query)
        scores = []
        
        for idx, doc_tf in enumerate(self.doc_term_freqs):
            score = 0.0
            doc_len = self.doc_lengths[idx]
            
            for term in query_tokens:
                if term not in doc_tf:
                    continue
                    
                tf = doc_tf[term]
                idf = self.idf.get(term, 0)
                
                # BM25 formula
                numerator = tf * (self.k1 + 1)
                if self.avg_doc_length > 0:
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
                else:
                    denominator = tf + self.k1
                score += idf * (numerator / denominator) if denominator > 0 else 0
            
            scores.append(score)
        
        return scores
    
    def get_top_k(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        """
        Get top-k documents by BM25 score.
        
        Returns:
            List of (doc_index, score) tuples sorted by score descending
        """
        scores = self.get_scores(query)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        return indexed_scores[:k]


def reciprocal_rank_fusion(
    rankings: List[List[Tuple[int, float]]],
    k: int = 60
) -> List[Tuple[int, float]]:
    """
    Combine multiple rankings using Reciprocal Rank Fusion (RRF).
    
    RRF score = sum(1 / (k + rank_i)) for each ranking
    
    Args:
        rankings: List of rankings, each is a list of (item_id, score) tuples
        k: Constant to prevent high scores for top-ranked items (default 60)
        
    Returns:
        Combined ranking as list of (item_id, rrf_score) tuples
    """
    rrf_scores = defaultdict(float)
    
    for ranking in rankings:
        for rank, (item_id, _) in enumerate(ranking, start=1):
            rrf_scores[item_id] += 1.0 / (k + rank)
    
    # Sort by RRF score descending
    combined = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return combined


class HybridSearchService:
    """
    Hybrid search combining vector similarity and BM25 keyword matching.
    """
    
    def __init__(self, vector_weight: float = 0.7, keyword_weight: float = 0.3):
        """
        Args:
            vector_weight: Weight for semantic/vector search results
            keyword_weight: Weight for keyword/BM25 search results
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.bm25 = BM25()
        self._corpus_cache = {}  # chunk_id -> content
        self._chunk_ids = []  # Ordered list of chunk IDs matching corpus order
        
    def build_keyword_index(self, chunks: List[Dict[str, Any]]):
        """
        Build the BM25 index from document chunks.
        
        Args:
            chunks: List of chunk dicts with 'id' and 'content' keys
        """
        self._corpus_cache = {c['id']: c for c in chunks}
        self._chunk_ids = [c['id'] for c in chunks]
        corpus = [c['content'] for c in chunks]
        self.bm25.fit(corpus)
        logger.info(f"Built BM25 index with {len(corpus)} chunks")
    
    def keyword_search(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        """
        Perform keyword search using BM25.
        
        Returns:
            List of (chunk_id, score) tuples
        """
        if not self._chunk_ids:
            return []
            
        top_k = self.bm25.get_top_k(query, k)
        
        # Convert corpus indices to chunk IDs
        results = []
        for corpus_idx, score in top_k:
            if corpus_idx < len(self._chunk_ids):
                chunk_id = self._chunk_ids[corpus_idx]
                results.append((chunk_id, score))
        
        return results
    
    def combine_results(
        self,
        vector_results: List[Tuple[int, float]],  # (chunk_id, similarity_score)
        keyword_results: List[Tuple[int, float]],  # (chunk_id, bm25_score)
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and keyword search results using RRF.
        
        Returns:
            Combined results with both scores and final ranking
        """
        # Use RRF to combine rankings
        combined = reciprocal_rank_fusion([vector_results, keyword_results])
        
        # Build result dicts with all scores
        results = []
        
        # Create lookup maps for scores and ranks
        vector_scores = {cid: score for cid, score in vector_results}
        keyword_scores = {cid: score for cid, score in keyword_results}
        vector_ranks = {cid: rank for rank, (cid, _) in enumerate(vector_results, 1)}
        keyword_ranks = {cid: rank for rank, (cid, _) in enumerate(keyword_results, 1)}
        
        # Normalize keyword scores to 0-1 range
        max_kw_score = max((s for _, s in keyword_results), default=1.0) or 1.0
        
        for chunk_id, rrf_score in combined[:k]:
            vec_score = vector_scores.get(chunk_id, 0.0)
            kw_score = keyword_scores.get(chunk_id, 0.0) / max_kw_score
            
            results.append({
                'chunk_id': chunk_id,
                'vector_score': vec_score,
                'keyword_score': kw_score,
                'combined_score': rrf_score,
                'vector_rank': vector_ranks.get(chunk_id, 999),
                'keyword_rank': keyword_ranks.get(chunk_id, 999)
            })
        
        return results
