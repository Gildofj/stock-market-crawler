from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    pool_size=20,          # Increase base connections
    max_overflow=40,       # Allow more spikes under load
    pool_timeout=30,       # Wait 30s before failing
    pool_recycle=1800,     # Reset connections every 30m
    pool_pre_ping=True     # Check if connection is alive before using
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
