import os

os.environ.setdefault("API_KEY", "test-api-key")

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crawler.models.models import Base
from crawler.repositories import (
    CompanyRepository,
    FundamentalRepository,
    PriceRepository,
    ReliabilityRepository,
)
from crawler.services.etl_service import ETLService
from crawler.services.lake_service import LakeService

TEST_API_KEY = os.environ["API_KEY"]
TEST_AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True, scope="session")
def _init_fastapi_cache():
    """TestClient does not run the FastAPI lifespan, so FastAPICache is
    never initialized in tests. Endpoints decorated with `@cache` would
    crash trying to reach a backend. Wire an in-memory backend once per
    session — harmless for tests that don't use caching.
    """
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

# Use a fast in-memory SQLite for core logic tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, tables):
    """
    Creates a new database session for a test, with a transaction that is rolled back.
    This is the fastest way to run database tests as it avoids disk I/O and re-seeding.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


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
