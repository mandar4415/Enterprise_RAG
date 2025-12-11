"""
Database migration script - adds new columns for authentication
"""
from sqlalchemy import text
from src.db import engine

def migrate():
    # Each operation in its own transaction to avoid cascading failures
    
    # 1. Add user_id to documents table
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE documents ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE'))
            conn.commit()
            print('✓ Added user_id to documents')
    except Exception as e:
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            print('- user_id already exists in documents')
        else:
            print(f'! user_id error: {e}')
    
    # 2. Add auth_provider to users table
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(50) DEFAULT 'email'"))
            conn.commit()
            print('✓ Added auth_provider to users')
    except Exception as e:
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            print('- auth_provider already exists in users')
        else:
            print(f'! auth_provider error: {e}')
    
    # 3. Create otp_codes table
    try:
        with engine.connect() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS otp_codes (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    code VARCHAR(10) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            conn.commit()
            print('✓ Created otp_codes table')
    except Exception as e:
        print(f'! otp_codes error: {e}')
    
    # 4. Create index on otp_codes.email
    try:
        with engine.connect() as conn:
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_otp_codes_email ON otp_codes(email)'))
            conn.commit()
            print('✓ Created index on otp_codes.email')
    except Exception as e:
        print(f'! otp index error: {e}')
    
    # 5. Create index on documents.user_id
    try:
        with engine.connect() as conn:
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id)'))
            conn.commit()
            print('✓ Created index on documents.user_id')
    except Exception as e:
        print(f'! documents index error: {e}')
    
    print('\n✅ Database migration complete!')

if __name__ == "__main__":
    migrate()
