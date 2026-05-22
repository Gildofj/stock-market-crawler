import os

os.environ.setdefault("API_KEY", "test-api-key")

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.models.models import Base
from core.repositories import (
    CompanyRepository,
    FundamentalRepository,
    PriceRepository,
    ReliabilityRepository,
)
from core.services.etl_service import ETLService
from core.services.lake_service import LakeService

TEST_API_KEY = os.environ["API_KEY"]
TEST_AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True, scope="session")
def _init_fastapi_cache():
    FastAPICache.init(InMemoryBackend(), prefix="test-cache")
    yield
    FastAPICache.reset()


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """InMemoryBackend's `_store` is a class-level dict, so cached entries
    leak across tests unless cleared. Reach in directly — `await
    backend.clear()` would require an event loop in every sync test.
    """
    InMemoryBackend._store.clear()
    yield
    InMemoryBackend._store.clear()


SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    return engine


@pytest.fixture
async def db_session(engine):
    """
    Creates a new database async session for a test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def company_repo(db_session):
    return CompanyRepository(db_session)


@pytest.fixture
def price_repo(db_session):
    return PriceRepository(db_session)


@pytest.fixture
def fundamental_repo(db_session):
    return FundamentalRepository(db_session)


@pytest.fixture
def reliability_repo(db_session):
    return ReliabilityRepository(db_session)


@pytest.fixture
def etl_service(db_session):
    return ETLService(db_session)


@pytest.fixture
def lake_service(db_session):
    return LakeService(db_session)
