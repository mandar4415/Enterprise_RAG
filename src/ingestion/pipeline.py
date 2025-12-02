"""
Document ingestion pipeline for Deep Agent - Policy Edition
Handles document processing, chunking, embedding generation, and storage
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from src.core.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DIMENSION
)
from src.db.models import Document, DocumentChunk
from src.db.connection import get_db_context
from src.utils.helpers import extract_text, clean_text, get_file_type


class EmbeddingModel:
    """
    Singleton class for the embedding model to avoid reloading.
    Uses sentence-transformers for generating embeddings.
    """
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return cls._instance
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            List of embedding vectors
        """
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def encode_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to encode
            
        Returns:
            Embedding vector as a list of floats
        """
        embedding = self._model.encode([text], convert_to_numpy=True)
        return embedding[0].tolist()


# Global embedding model instance
embedding_model = EmbeddingModel()


def chunk_text(text: str) -> List[Dict[str, Any]]:
    """
    Split text into chunks using LangChain's RecursiveCharacterTextSplitter.
    Optimized for policy documents with proper overlap for context.
    
    Args:
        text: Full document text
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]  # Prioritize paragraph breaks
    )
    
    # Split the text
    chunks = text_splitter.split_text(text)
    
    # Add metadata to each chunk
    chunk_data = []
    current_position = 0
    
    for idx, chunk_content in enumerate(chunks):
        # Find the start position of this chunk in the original text
        start_char = text.find(chunk_content, current_position)
        if start_char == -1:
            start_char = current_position
        end_char = start_char + len(chunk_content)
        
        chunk_data.append({
            "content": chunk_content,
            "chunk_index": idx,
            "start_char": start_char,
            "end_char": end_char
        })
        
        # Move position forward, accounting for overlap
        current_position = max(start_char + 1, current_position)
    
    return chunk_data


def generate_embeddings(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for each chunk.
    
    Args:
        chunks: List of chunk dictionaries
        
    Returns:
        List of chunks with embeddings added
    """
    # Extract content for batch encoding
    texts = [chunk["content"] for chunk in chunks]
    
    # Generate embeddings in batch for efficiency
    embeddings = embedding_model.encode(texts)
    
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
    
    def store_to_db(session: Session) -> Document:
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
        
        # Create chunk records
        for chunk_data in chunks_with_embeddings:
            chunk = DocumentChunk(
                document_id=document.id,
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                start_char=chunk_data["start_char"],
                end_char=chunk_data["end_char"],
                embedding=chunk_data["embedding"]
            )
            session.add(chunk)
        
        return document
    
    # Use provided session or create a new one
    if db:
        document = store_to_db(db)
        db.commit()
    else:
        with get_db_context() as session:
            document = store_to_db(session)
    
    print(f"Document ingested successfully! ID: {document.id}")
    
    return {
        "document_id": document.id,
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