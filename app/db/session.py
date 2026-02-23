from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# 1. ADD THIS IMPORT:
from sqlalchemy.ext.declarative import declarative_base 
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. DEFINE BASE HERE (So models can import it):
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()