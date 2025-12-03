"""
Document ingestion pipeline for Deep Agent - Policy Edition
Handles document processing, chunking, embedding generation, and storage

Improvements:
- Nomic Embed v1.5 with Matryoshka support for flexible dimensions
- Semantic chunking for better context preservation
- Metadata filtering to improve context precision
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
import torch.nn.functional as F
import torch

from src.core.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DIMENSION,
    MATRYOSHKA_DIM,
    EMBEDDING_PREFIX_DOCUMENT,
    EMBEDDING_PREFIX_QUERY,
    ENABLE_SEMANTIC_CHUNKING,
    SEMANTIC_CHUNK_BREAKPOINT_THRESHOLD,
    FILTER_METADATA_CHUNKS,
    METADATA_KEYWORDS
)
from src.db.models import Document, DocumentChunk
from src.db.connection import get_db_context
from src.utils.helpers import extract_text, clean_text, get_file_type


class EmbeddingModel:
    """
    Singleton class for the embedding model.
    Uses nomic-embed-text-v1.5 with Matryoshka support for flexible dimensions.
    """
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            cls._model = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)
            print(f"Embedding model loaded! Using dimension: {MATRYOSHKA_DIM}")
        return cls._instance
    
    def _apply_matryoshka(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Apply Matryoshka dimension reduction with proper normalization.
        
        Args:
            embeddings: Full-dimension embeddings
            
        Returns:
            Reduced dimension embeddings
        """
        # Convert to tensor for processing
        tensor = torch.from_numpy(embeddings).float()
        
        # Apply layer normalization
        tensor = F.layer_norm(tensor, normalized_shape=(tensor.shape[1],))
        
        # Truncate to Matryoshka dimension
        tensor = tensor[:, :MATRYOSHKA_DIM]
        
        # L2 normalize
        tensor = F.normalize(tensor, p=2, dim=1)
        
        return tensor.numpy()
    
    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with task-specific prefixes.
        
        Args:
            texts: List of text strings to encode
            is_query: If True, use query prefix; else use document prefix
            
        Returns:
            List of embedding vectors
        """
        # Add task-specific prefix for nomic-embed
        prefix = EMBEDDING_PREFIX_QUERY if is_query else EMBEDDING_PREFIX_DOCUMENT
        prefixed_texts = [prefix + text for text in texts]
        
        # Generate embeddings
        embeddings = self._model.encode(prefixed_texts, convert_to_numpy=True)
        
        # Apply Matryoshka dimension reduction
        reduced_embeddings = self._apply_matryoshka(embeddings)
        
        return reduced_embeddings.tolist()
    
    def encode_single(self, text: str, is_query: bool = False) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to encode
            is_query: If True, use query prefix; else use document prefix
            
        Returns:
            Embedding vector as a list of floats
        """
        result = self.encode([text], is_query=is_query)
        return result[0]
    
    def encode_for_similarity(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts for semantic similarity comparison (used in semantic chunking).
        Uses clustering prefix for better sentence-level similarity.
        
        Args:
            texts: List of sentences to compare
            
        Returns:
            Numpy array of embeddings
        """
        prefixed_texts = ["clustering: " + text for text in texts]
        embeddings = self._model.encode(prefixed_texts, convert_to_numpy=True)
        return self._apply_matryoshka(embeddings)


# Global embedding model instance
embedding_model = EmbeddingModel()


def is_metadata_chunk(text: str) -> bool:
    """
    Check if a chunk appears to be metadata/header content.
    
    Args:
        text: Chunk content to check
        
    Returns:
        True if chunk appears to be metadata
    """
    if not FILTER_METADATA_CHUNKS:
        return False
    
    text_lower = text.lower()
    
    # Check for metadata keywords
    for keyword in METADATA_KEYWORDS:
        if keyword in text_lower:
            return True
    
    # Check for very short chunks (likely headers)
    if len(text.strip()) < 100:
        return True
    
    # Check for excessive special characters (likely tables/formatting)
    special_ratio = sum(1 for c in text if c in '|_-=[]{}()<>') / max(len(text), 1)
    if special_ratio > 0.15:
        return True
    
    return False


def semantic_chunk_text(text: str) -> List[Dict[str, Any]]:
    """
    Split text using semantic chunking - splits on meaning boundaries.
    Uses embedding similarity to detect topic changes.
    
    Args:
        text: Full document text
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    # Split into sentences first
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) < 3:
        # Too few sentences, use fallback
        return fallback_chunk_text(text)
    
    try:
        # Get embeddings for all sentences
        embeddings = embedding_model.encode_for_similarity(sentences)
        
        # Calculate similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        
        # Find breakpoints where similarity drops significantly
        breakpoints = [0]  # Start of first chunk
        threshold = SEMANTIC_CHUNK_BREAKPOINT_THRESHOLD
        
        for i, sim in enumerate(similarities):
            if sim < threshold:
                breakpoints.append(i + 1)
        
        breakpoints.append(len(sentences))  # End of last chunk
        
        # Create chunks from breakpoints
        chunks = []
        current_position = 0
        
        for i in range(len(breakpoints) - 1):
            start_idx = breakpoints[i]
            end_idx = breakpoints[i + 1]
            
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_content = ' '.join(chunk_sentences)
            
            # Skip if chunk is too small
            if len(chunk_content) < 50:
                continue
            
            # Find position in original text
            start_char = text.find(chunk_sentences[0], current_position)
            if start_char == -1:
                start_char = current_position
            
            end_char = start_char + len(chunk_content)
            
            chunks.append({
                "content": chunk_content,
                "chunk_index": len(chunks),
                "start_char": start_char,
                "end_char": end_char,
                "is_metadata": is_metadata_chunk(chunk_content)
            })
            
            current_position = end_char
        
        # If semantic chunking produced too few chunks, use fallback
        if len(chunks) < 2:
            return fallback_chunk_text(text)
        
        return chunks
        
    except Exception as e:
        print(f"Semantic chunking failed, using fallback: {e}")
        return fallback_chunk_text(text)


def fallback_chunk_text(text: str) -> List[Dict[str, Any]]:
    """
    Fallback to character-based chunking when semantic chunking fails.
    
    Args:
        text: Full document text
        
    Returns:
        List of chunk dictionaries
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks_text = text_splitter.split_text(text)
    
    chunk_data = []
    current_position = 0
    
    for idx, chunk_content in enumerate(chunks_text):
        start_char = text.find(chunk_content, current_position)
        if start_char == -1:
            start_char = current_position
        end_char = start_char + len(chunk_content)
        
        chunk_data.append({
            "content": chunk_content,
            "chunk_index": idx,
            "start_char": start_char,
            "end_char": end_char,
            "is_metadata": is_metadata_chunk(chunk_content)
        })
        
        current_position = max(start_char + 1, current_position)
    
    return chunk_data


def chunk_text(text: str) -> List[Dict[str, Any]]:
    """
    Split text into chunks using semantic or character-based chunking.
    Optimized for policy documents with proper overlap for context.
    
    Args:
        text: Full document text
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    if ENABLE_SEMANTIC_CHUNKING:
        return semantic_chunk_text(text)
    else:
        return fallback_chunk_text(text)


def generate_embeddings(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for each chunk using document prefix.
    
    Args:
        chunks: List of chunk dictionaries
        
    Returns:
        List of chunks with embeddings added
    """
    # Extract content for batch encoding
    texts = [chunk["content"] for chunk in chunks]
    
    # Generate embeddings in batch with document prefix
    embeddings = embedding_model.encode(texts, is_query=False)
    
    # Add embeddings to chunks
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
    
    return chunks


def ingest_document(
    file_path: str,
    filename: str,
    file_size: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Full document ingestion pipeline: extract, clean, chunk, embed, and store.
    
    Args:
        file_path: Path to the uploaded document file
        filename: Original filename
        file_size: Size of the file in bytes
        title: Optional document title
        description: Optional document description
        db: Optional database session (will create one if not provided)
        
    Returns:
        Dictionary with ingestion results
    """
    # Step 1: Extract text from document
    print(f"Extracting text from {filename}...")
    raw_text = extract_text(file_path)
    
    # Step 2: Clean the extracted text
    print("Cleaning text...")
    cleaned_text = clean_text(raw_text)
    
    if not cleaned_text.strip():
        raise ValueError("Document contains no extractable text content")
    
    # Step 3: Chunk the text
    print("Chunking text...")
    chunks = chunk_text(cleaned_text)
    print(f"Created {len(chunks)} chunks")
    
    # Step 4: Generate embeddings
    print("Generating embeddings...")
    chunks_with_embeddings = generate_embeddings(chunks)
    
    # Step 5: Store in database
    print("Storing in database...")
    
    def store_to_db(session: Session) -> int:
        # Create document record
        document = Document(
            filename=filename,
            file_type=get_file_type(filename),
            file_size=file_size,
            title=title or filename,
            description=description
        )
        session.add(document)
        session.flush()  # Get the document ID
        
        # Store the ID before we lose access to the object
        doc_id = document.id
        
        # Create chunk records
        for chunk_data in chunks_with_embeddings:
            chunk = DocumentChunk(
                document_id=doc_id,
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                start_char=chunk_data["start_char"],
                end_char=chunk_data["end_char"],
                embedding=chunk_data["embedding"]
            )
            session.add(chunk)
        
        return doc_id
    
    # Use provided session or create a new one
    if db:
        document_id = store_to_db(db)
        db.commit()
    else:
        with get_db_context() as session:
            document_id = store_to_db(session)
    
    print(f"Document ingested successfully! ID: {document_id}")
    
    return {
        "document_id": document_id,
        "filename": filename,
        "file_type": get_file_type(filename),
        "file_size": file_size,
        "num_chunks": len(chunks),
        "title": title or filename,
        "status": "success"
    }


def delete_document(document_id: int, db: Optional[Session] = None) -> bool:
    """
    Delete a document and all its chunks from the database.
    
    Args:
        document_id: ID of the document to delete
        db: Optional database session
        
    Returns:
        True if document was deleted, False if not found
    """
    def do_delete(session: Session) -> bool:
        document = session.query(Document).filter(Document.id == document_id).first()
        if document:
            session.delete(document)
            return True
        return False
    
    if db:
        result = do_delete(db)
        db.commit()
        return result
    else:
        with get_db_context() as session:
            return do_delete(session)


def get_document_info(document_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Get information about a stored document.
    
    Args:
        document_id: ID of the document
        db: Optional database session
        
    Returns:
        Document information dictionary or None if not found
    """
    def do_get(session: Session) -> Optional[Dict[str, Any]]:
        document = session.query(Document).filter(Document.id == document_id).first()
        if document:
            return {
                "id": document.id,
                "filename": document.filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "title": document.title,
                "description": document.description,
                "num_chunks": len(document.chunks),
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat()
            }
        return None
    
    if db:
        return do_get(db)
    else:
        with get_db_context() as session:
            return do_get(session)


def list_documents(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    List all documents in the database.
    
    Args:
        db: Optional database session
        
    Returns:
        List of document information dictionaries
    """
    def do_list(session: Session) -> List[Dict[str, Any]]:
        documents = session.query(Document).all()
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "title": doc.title,
                "num_chunks": len(doc.chunks),
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ]
    
    if db:
        return do_list(db)
    else:
        with get_db_context() as session:
            return do_list(session)


def check_duplicate_document(
    filename: str,
    file_size: int,
    db: Optional[Session] = None
) -> Optional[Dict[str, Any]]:
    """
    Check if a document with the same filename and size already exists.
    
    Args:
        filename: Name of the file to check
        file_size: Size of the file in bytes
        db: Optional database session
        
    Returns:
        Document info dict if duplicate found, None otherwise
    """
    def do_check(session: Session) -> Optional[Dict[str, Any]]:
        # Check for exact match on filename and file_size
        existing = session.query(Document).filter(
            Document.filename == filename,
            Document.file_size == file_size
        ).first()
        
        if existing:
            return {
                "id": existing.id,
                "filename": existing.filename,
                "title": existing.title,
                "created_at": existing.created_at.isoformat()
            }
        return None
    
    if db:
        return do_check(db)
    else:
        with get_db_context() as session:
            return do_check(session)