import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import app
from crawler.models.models import Company
from crawler.services.database import get_db as get_crawler_db

client = TestClient(app)


@pytest.fixture
def override_db(db_session: Session):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_crawler_db] = _override_db
    yield
    app.dependency_overrides.clear()


def test_search_companies(db_session: Session, override_db):
    # Seed data
    c1 = Company(symbol="PETR4", name="Petrobras PN", sector="Energy")
    c2 = Company(symbol="VALE3", name="Vale ON", sector="Mining")
    c3 = Company(symbol="ITUB4", name="Itaú Unibanco PN", sector="Financial")
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    # Test search by symbol (exact)
    response = client.get("/api/v1/companies/search?q=PETR4")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "PETR4"

    # Test search by symbol (partial)
    response = client.get("/api/v1/companies/search?q=TU")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "ITUB4"

    # Test search by name (partial)
    response = client.get("/api/v1/companies/search?q=bras")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Petrobras PN"

    # Test search with limit
    response = client.get("/api/v1/companies/search?q=P&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    # Test search no results
    response = client.get("/api/v1/companies/search?q=XYZ")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_search_min_length(override_db):
    # Test min length constraint (q must be at least 1 char, which is handled by Query)
    # If q is empty, FastAPI should return 422 Unprocessable Entity
    response = client.get("/api/v1/companies/search?q=")
    assert response.status_code == 422
