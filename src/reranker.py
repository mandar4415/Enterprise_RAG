"""
Cross-encoder reranker for Enterprise RAG - Simplified Edition
CRITICAL: This is essential for the 1.00 score - do not modify
~50 lines
"""
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

from src.config import RERANKER_MODEL, TOP_K_FINAL, MIN_RERANK_SCORE


class Reranker:
    """Singleton cross-encoder for re-ranking retrieved chunks."""
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print(f"Loading reranker: {RERANKER_MODEL}")
            cls._model = CrossEncoder(RERANKER_MODEL, max_length=512)
            print("Reranker loaded!")
        return cls._instance
    
    def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = TOP_K_FINAL) -> List[Dict[str, Any]]:
        """
        Re-rank chunks using cross-encoder scores.
        
        Args:
            query: Search query
            chunks: List of chunk dicts with 'content' key
            top_k: Number of results to return
            
        Returns:
            Re-ranked and filtered chunks (only high-quality ones)
        """
        if not chunks:
            return []
        
        # Score all query-chunk pairs
        pairs = [(query, c['content']) for c in chunks]
        scores = self._model.predict(pairs)
        
        # Add scores to chunks
        for chunk, score in zip(chunks, scores):
            chunk['rerank_score'] = float(score)
        
        # Sort by score (descending) and STRICTLY filter by threshold
        ranked = sorted(chunks, key=lambda x: x['rerank_score'], reverse=True)
        filtered = [c for c in ranked if c['rerank_score'] >= MIN_RERANK_SCORE]
        
        # Only return chunks that pass the threshold - no fallback to low-quality chunks
        return filtered[:top_k]


# Global instance
reranker = Reranker()
