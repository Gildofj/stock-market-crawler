import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from api.main import app
from crawler.models.models import Company, StockPrice, Fundamental
from crawler.services.database import get_db as get_crawler_db

client = TestClient(app)

@pytest.fixture
def override_db(db_session: Session):
    def _override_db():
        yield db_session
    
    app.dependency_overrides[get_crawler_db] = _override_db
    yield
    app.dependency_overrides.clear()

def test_search_includes_id(db_session: Session, override_db):
    # Seed data
    c1 = Company(symbol="PETR4", name="Petrobras PN")
    db_session.add(c1)
    db_session.commit()

    # Test search endpoint
    response = client.get("/api/v1/companies/search?q=PETR4")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "id" in data[0]
    assert uuid.UUID(data[0]["id"]) == c1.id

def test_get_prices_by_id(db_session: Session, override_db):
    # Seed data
    c1 = Company(symbol="PETR4", name="Petrobras PN")
    db_session.add(c1)
    db_session.flush()

    p1 = StockPrice(time=datetime.now(), company_id=c1.id, close=30.50)
    db_session.add(p1)
    db_session.commit()

    # Test GET /prices/{uuid}
    response = client.get(f"/api/v1/prices/{c1.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert float(data[0]["close"]) == 30.50

def test_get_fundamentals_by_id(db_session: Session, override_db):
    # Seed data
    c1 = Company(symbol="VALE3", name="Vale ON")
    db_session.add(c1)
    db_session.flush()

    f1 = Fundamental(company_id=c1.id, p_l=5.5, collected_at=datetime.now())
    db_session.add(f1)
    db_session.commit()

    # Test GET /fundamentals/{uuid}
    response = client.get(f"/api/v1/fundamentals/{c1.id}")
    assert response.status_code == 200
    data = response.json()
    assert float(data["p_l"]) == 5.5

def test_not_found_errors_by_id(override_db):
    random_id = uuid.uuid4()
    assert client.get(f"/api/v1/prices/{random_id}").status_code == 404
    assert client.get(f"/api/v1/fundamentals/{random_id}").status_code == 404
