from sqlalchemy import create_engine
from src.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
