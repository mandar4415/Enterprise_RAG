"""
Database connection module for Deep Agent - Policy Edition
Handles database engine creation, session management, and initialization
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from src.core.config import DATABASE_URL


# Create the database engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Enable connection health checks
    echo=False  # Set to True for SQL query logging during debugging
)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    Use this with FastAPI's Depends() for automatic session management.
    
    Yields:
        Session: A SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Use this when you need a session outside of FastAPI endpoints.
    
    Example:
        with get_db_context() as db:
            documents = db.query(Document).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating the pgvector extension
    and all tables defined in the models.
    
    This should be called once at application startup.
    """
    from src.db.models import Base
    
    # Create pgvector extension if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("Database initialized successfully!")


def check_connection() -> bool:
    """
    Check if the database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
