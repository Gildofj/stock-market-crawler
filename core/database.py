from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from core.config import settings

# Global variables for lazy initialization
_engine = None
_AsyncSessionLocal = None
Base = declarative_base()


def get_engine():
    """Lazy initialize the SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        # Re-read settings or get URL directly to ensure patch from main.py is applied
        db_url = settings.database_url
        _engine = create_async_engine(
            db_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )
    return _engine


def session_local() -> AsyncSession:
    """Lazy initialize and return a new AsyncSession instance."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(), class_=AsyncSession
        )
    return _AsyncSessionLocal()


async def get_db():
    db = session_local()
    try:
        yield db
    finally:
        await db.close()
