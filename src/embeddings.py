"""
Embedding model for Enterprise RAG - Simplified Edition
Nomic Embed v1.5 with Matryoshka support (~70 lines)
CRITICAL: This is essential for the 1.00 score - do not modify
"""
from typing import List
import numpy as np
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

from src.config import EMBEDDING_MODEL, EMBEDDING_DIM, EMBEDDING_PREFIX_DOC, EMBEDDING_PREFIX_QUERY


class Embedder:
    """
    Singleton embedding model using Nomic Embed v1.5.
    Uses Matryoshka dimension reduction for efficient storage.
    """
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print(f"Loading embedding model: {EMBEDDING_MODEL}")
            cls._model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
            print(f"Model loaded! Dimension: {EMBEDDING_DIM}")
        return cls._instance
    
    def _reduce_dim(self, embeddings: np.ndarray) -> np.ndarray:
        """Apply Matryoshka dimension reduction with normalization."""
        tensor = torch.from_numpy(embeddings).float()
        tensor = F.layer_norm(tensor, normalized_shape=(tensor.shape[1],))
        tensor = tensor[:, :EMBEDDING_DIM]
        tensor = F.normalize(tensor, p=2, dim=1)
        return tensor.numpy()
    
    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """
        Generate embeddings with task-specific prefixes.
        
        Args:
            texts: List of texts to encode
            is_query: True for queries, False for documents
            
        Returns:
            List of embedding vectors
        """
        prefix = EMBEDDING_PREFIX_QUERY if is_query else EMBEDDING_PREFIX_DOC
        prefixed = [prefix + t for t in texts]
        embeddings = self._model.encode(prefixed, convert_to_numpy=True)
        return self._reduce_dim(embeddings).tolist()
    
    def encode_single(self, text: str, is_query: bool = False) -> List[float]:
        """Encode a single text."""
        return self.encode([text], is_query)[0]


# Global instance
embedder = Embedder()
