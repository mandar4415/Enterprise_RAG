"""
Database models and connection for Enterprise RAG - Simplified Edition
Combined models + connection in ~90 lines
"""
from datetime import datetime
from contextlib import contextmanager
from typing import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from pgvector.sqlalchemy import Vector

import os
from src.config import DATABASE_URL, EMBEDDING_DIM

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def _get_encoded_url() -> str:
    """Handle special characters in database URL by constructing from parts."""
    # Get individual parts from env (more reliable than parsing URL with special chars)
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "deepagent")
    
    # URL-encode password for special characters
    encoded_password = quote_plus(password) if password else ""
    return f"postgresql+psycopg2://{user}:{encoded_password}@{host}:{port}/{name}"

engine = create_engine(_get_encoded_url(), pool_size=5, max_overflow=10, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """Initialize database with pgvector extension and tables."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    print("Database initialized!")

def check_db() -> bool:
    """Check database connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

# =============================================================================
# MODELS
# =============================================================================

Base = declarative_base()

class Document(Base):
    """Policy document metadata."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    title = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    """Document chunk with embedding."""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    start_char = Column(Integer)
    end_char = Column(Integer)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = (
        Index('ix_chunks_embedding', embedding,
              postgresql_using='hnsw',
              postgresql_with={'m': 16, 'ef_construction': 64},
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )
