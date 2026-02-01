from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Create the Database Engine
# We pass the URL we constructed in config.py
# pool_pre_ping=True handles "stale" connections gracefully
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# 2. Create a Session Factory
# This is what generates a new "handle" to the database for every request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. The Dependency
# In FastAPI, we use this function to get a database session for a single request,
# and ensure it closes automatically when the request is done.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()