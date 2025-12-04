"""
Cross-encoder reranker for Enterprise RAG - Simplified Edition
CRITICAL: This is essential for the 1.00 score - do not modify
"""
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

from src.config import RERANKER_MODEL, TOP_K_FINAL, MIN_RERANK_SCORE


def normalize_score(raw_score: float, min_score: float = -10.0, max_score: float = 10.0) -> float:
    """
    Normalize raw cross-encoder score to 0-1 range for display.
    Uses min-max scaling with typical score range.
    """
    # Clamp to expected range
    clamped = max(min_score, min(max_score, raw_score))
    # Scale to 0-1
    normalized = (clamped - min_score) / (max_score - min_score)
    return round(normalized, 3)


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
        raw_scores = self._model.predict(pairs)
        
        # Add scores to chunks
        # raw_score: original logit (-10 to +10 range) - used for filtering
        # rerank_score: normalized to 0-1 for display
        for chunk, raw_score in zip(chunks, raw_scores):
            chunk['raw_score'] = float(raw_score)
            chunk['rerank_score'] = normalize_score(float(raw_score))
        
        # Sort by raw score (descending) and filter by threshold
        ranked = sorted(chunks, key=lambda x: x['raw_score'], reverse=True)
        filtered = [c for c in ranked if c['raw_score'] >= MIN_RERANK_SCORE]
        
        # Only return chunks that pass the threshold
        return filtered[:top_k]


# Global instance
reranker = Reranker()
