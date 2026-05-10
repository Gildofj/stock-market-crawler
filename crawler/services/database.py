from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# Global variables for lazy initialization
_engine = None
_SessionLocal = None
Base = declarative_base()


def get_engine():
    """Lazy initialize the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        # Re-read settings or get URL directly to ensure patch from main.py is applied
        db_url = settings.database_url
        _engine = create_engine(
            db_url,
            pool_size=20,
            max_overflow=40,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True
        )
    return _engine


def session_local():
    """Lazy initialize and return a new session_local instance."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal()


def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()
