"""
Re-ranking module for Deep Agent - Policy Edition
Implements cross-encoder re-ranking to improve context precision

The Problem:
- Bi-encoder embeddings (sentence-transformers) are fast but less accurate
- They often retrieve semantically similar but not actually relevant chunks
- This leads to low context precision (irrelevant chunks in results)

The Solution:
- Use a cross-encoder to re-rank initial retrieval results
- Cross-encoders are slower but much more accurate at scoring relevance
- They consider query and document together, not separately
"""
from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
import numpy as np

from src.core.config import (
    TOP_K_AFTER_RERANK,
    MIN_RELEVANCE_SCORE,
    ENABLE_RERANKING
)


class ReRanker:
    """
    Cross-encoder based re-ranker for improving retrieval precision.
    Uses a lightweight cross-encoder model for scoring query-document pairs.
    """
    _instance = None
    _model = None
    
    # Cross-encoder model options (from smallest to largest):
    # - cross-encoder/ms-marco-MiniLM-L-6-v2 (22MB, fast)
    # - cross-encoder/ms-marco-MiniLM-L-12-v2 (33MB, balanced)  
    # - cross-encoder/ms-marco-TinyBERT-L-6 (17MB, very fast)
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if ENABLE_RERANKING:
                print(f"Loading re-ranking model: {cls.MODEL_NAME}")
                cls._model = CrossEncoder(cls.MODEL_NAME, max_length=512)
                print("Re-ranking model loaded!")
        return cls._instance
    
    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = TOP_K_AFTER_RERANK
    ) -> List[Dict[str, Any]]:
        """
        Re-rank chunks based on relevance to the query using cross-encoder.
        
        Args:
            query: The search query
            chunks: List of retrieved chunk dictionaries
            top_k: Number of top results to return after re-ranking
            
        Returns:
            Re-ranked list of chunks with updated relevance scores
        """
        if not chunks:
            return []
        
        if not ENABLE_RERANKING or self._model is None:
            # If re-ranking is disabled, just return top_k chunks
            return chunks[:top_k]
        
        # Create query-document pairs for cross-encoder
        pairs = [(query, chunk['content']) for chunk in chunks]
        
        # Score all pairs
        scores = self._model.predict(pairs)
        
        # Add cross-encoder scores to chunks
        for chunk, score in zip(chunks, scores):
            chunk['rerank_score'] = float(score)
            # Combine original similarity with rerank score (weighted)
            original_sim = chunk.get('similarity_score', 0.5)
            # Weight: 70% cross-encoder, 30% embedding similarity
            chunk['combined_score'] = 0.7 * float(score) + 0.3 * original_sim
        
        # Sort by combined score (descending)
        reranked = sorted(chunks, key=lambda x: x['combined_score'], reverse=True)
        
        # Filter by minimum relevance threshold
        filtered = [
            chunk for chunk in reranked 
            if chunk['rerank_score'] >= MIN_RELEVANCE_SCORE
        ]
        
        # If filtering removed all chunks, keep top results anyway
        if not filtered:
            filtered = reranked[:top_k]
        
        return filtered[:top_k]
    
    def score_single(self, query: str, document: str) -> float:
        """
        Score a single query-document pair.
        
        Args:
            query: The search query
            document: Document text to score
            
        Returns:
            Relevance score
        """
        if not ENABLE_RERANKING or self._model is None:
            return 0.5  # Default score
        
        score = self._model.predict([(query, document)])[0]
        return float(score)


# Global re-ranker instance
reranker = ReRanker()


def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = TOP_K_AFTER_RERANK
) -> List[Dict[str, Any]]:
    """
    Convenience function to re-rank chunks.
    
    Args:
        query: The search query
        chunks: List of retrieved chunks
        top_k: Number of results to return
        
    Returns:
        Re-ranked chunks
    """
    return reranker.rerank(query, chunks, top_k)


def filter_by_relevance(
    chunks: List[Dict[str, Any]],
    threshold: float = MIN_RELEVANCE_SCORE
) -> List[Dict[str, Any]]:
    """
    Filter chunks by relevance score threshold.
    
    Args:
        chunks: List of chunks with scores
        threshold: Minimum score to keep
        
    Returns:
        Filtered chunks
    """
    return [
        chunk for chunk in chunks
        if chunk.get('rerank_score', chunk.get('similarity_score', 0)) >= threshold
    ]
