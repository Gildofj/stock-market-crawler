from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from core.config import settings

_engine = None
_AsyncSessionLocal = None
Base = declarative_base()


def get_engine():
    global _engine
    if _engine is None:
        db_url = settings.database_url
        _engine = create_async_engine(
            db_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            # LIFO favours recently-released connections, keeping the working
            # set "hot" under bursty Cloud Tasks fan-out and letting idle
            # connections age out via pool_recycle.
            pool_use_lifo=True,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "server_settings": {
                    "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                },
            },
        )
    return _engine


def session_local() -> AsyncSession:
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
