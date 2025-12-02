"""
Database models for Deep Agent - Policy Edition
Contains SQLAlchemy models for documents and document chunks with pgvector support
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector

from src.core.config import EMBEDDING_DIMENSION

# Create the declarative base
Base = declarative_base()


class Document(Base):
    """
    Represents an uploaded policy document.
    Stores metadata about the original document.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt
    file_size = Column(Integer, nullable=False)  # Size in bytes
    
    # Document metadata
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to chunks
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}')>"


class DocumentChunk(Base):
    """
    Represents a chunk of a document with its vector embedding.
    Used for semantic search and retrieval.
    """
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Chunk content and metadata
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Position in the original document
    
    # Start and end character positions in the original document
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    
    # Vector embedding for semantic search
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to document
    document = relationship("Document", back_populates="chunks")

    # Index for vector similarity search using HNSW
    __table_args__ = (
        Index(
            'ix_document_chunks_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
