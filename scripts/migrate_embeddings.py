"""
Migration script to update embedding dimensions from 384 to 512.
This script:
1. Drops the old vector index
2. Clears old embeddings (sets to NULL)
3. Alters the embedding column dimension
4. Re-generates embeddings for all existing chunks
5. Recreates the vector index

Run this script after updating to nomic-embed-text-v1.5
"""
import sys
sys.path.insert(0, 'c:\\Users\\Lenovo\\OneDrive\\Attachments\\Desktop\\Entrp_Rag\\deep-agent-backend')

from sqlalchemy import text
from src.db.connection import engine, get_db_context
from src.ingestion.pipeline import embedding_model
from src.db.models import DocumentChunk
from src.core.config import EMBEDDING_DIMENSION


def migrate_embeddings():
    """Migrate embeddings to new dimension."""
    print(f"Starting migration to {EMBEDDING_DIMENSION} dimensions...")
    
    with engine.connect() as conn:
        # Step 1: Drop the old index
        print("Dropping old vector index...")
        try:
            conn.execute(text("DROP INDEX IF EXISTS ix_document_chunks_embedding"))
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not drop index: {e}")
        
        # Step 2: Drop NOT NULL constraint, drop column, and recreate
        print(f"Recreating embedding column with {EMBEDDING_DIMENSION} dimensions...")
        try:
            # Drop the old column entirely
            conn.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding"))
            conn.commit()
            
            # Add new column with correct dimension (nullable initially)
            conn.execute(text(f"ALTER TABLE document_chunks ADD COLUMN embedding vector({EMBEDDING_DIMENSION})"))
            conn.commit()
            print("Column recreated successfully!")
        except Exception as e:
            print(f"Error recreating column: {e}")
            return False
    
    # Step 3: Re-generate embeddings for all chunks
    print("Re-generating embeddings for all chunks...")
    with get_db_context() as session:
        chunks = session.query(DocumentChunk).all()
        total = len(chunks)
        print(f"Found {total} chunks to update...")
        
        if total == 0:
            print("No chunks to update.")
        else:
            batch_size = 50
            for i in range(0, total, batch_size):
                batch = chunks[i:i+batch_size]
                texts = [chunk.content for chunk in batch]
                
                # Generate new embeddings with document prefix
                embeddings = embedding_model.encode(texts, is_query=False)
                
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding
                
                session.flush()
                print(f"  Updated {min(i+batch_size, total)}/{total} chunks...")
            
            session.commit()
    
    # Step 4: Add NOT NULL constraint back
    print("Adding NOT NULL constraint...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE document_chunks ALTER COLUMN embedding SET NOT NULL"))
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not add NOT NULL constraint: {e}")
    
    # Step 5: Recreate the index
    print("Recreating vector index...")
    with engine.connect() as conn:
        try:
            conn.execute(text(f"""
                CREATE INDEX ix_document_chunks_embedding 
                ON document_chunks 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
            conn.commit()
            print("Index created successfully!")
        except Exception as e:
            print(f"Warning: Could not create index: {e}")
    
    print("\n✅ Migration complete!")
    return True


def check_current_dimension():
    """Check the current embedding dimension in the database."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT atttypmod 
            FROM pg_attribute 
            WHERE attrelid = 'document_chunks'::regclass 
            AND attname = 'embedding'
        """))
        row = result.fetchone()
        if row:
            # atttypmod for vector is dimension + 4
            current_dim = row[0] - 4 if row[0] > 0 else "unknown"
            print(f"Current embedding dimension: {current_dim}")
            return current_dim
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("Embedding Migration Script")
    print("=" * 60)
    
    current = check_current_dimension()
    
    if current == EMBEDDING_DIMENSION:
        print(f"\nDatabase already at {EMBEDDING_DIMENSION} dimensions. No migration needed.")
    else:
        print(f"\nMigrating from {current} to {EMBEDDING_DIMENSION} dimensions...")
        
        confirm = input("\n⚠️  This will re-generate all embeddings. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            migrate_embeddings()
        else:
            print("Migration cancelled.")
