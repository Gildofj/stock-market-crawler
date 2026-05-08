import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from crawler.services.database import Base
from crawler.services.data_service import DataService
from crawler.services.etl_service import ETLService

# Use a fast in-memory SQLite for core logic tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="session")
def Tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(engine, Tables):
    """
    Creates a new database session for a test, with a transaction that is rolled back.
    This is the fastest way to run database tests as it avoids disk I/O and re-seeding.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

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
