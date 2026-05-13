import os

os.environ.setdefault("API_KEY", "test-api-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crawler.models.models import Base
from crawler.services.data_service import DataService
from crawler.services.etl_service import ETLService

TEST_API_KEY = os.environ["API_KEY"]
TEST_AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}

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
def data_service(db_session):
    return DataService(db_session)


@pytest.fixture
def etl_service(db_session):
    return ETLService(db_session)
