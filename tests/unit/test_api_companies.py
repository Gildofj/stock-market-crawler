import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from core.database import get_db as get_crawler_db
from core.models.models import Company
from tests.conftest import TEST_AUTH_HEADERS

client = TestClient(app, headers=TEST_AUTH_HEADERS)


@pytest.fixture
def override_db(db_session: AsyncSession):
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_crawler_db] = _override_db
    yield db_session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_companies(db_session: AsyncSession, override_db):
    c1 = Company(symbol="PETR4", name="Petrobras PN", sector="Energy")
    c2 = Company(symbol="VALE3", name="Vale ON", sector="Mining")
    c3 = Company(symbol="ITUB4", name="Itaú Unibanco PN", sector="Financial")
    db_session.add_all([c1, c2, c3])
    await db_session.commit()

    response = client.get("/api/v1/companies/search?q=PETR4")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "PETR4"

    response = client.get("/api/v1/companies/search?q=TU")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "ITUB4"

    response = client.get("/api/v1/companies/search?q=bras")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Petrobras PN"

    response = client.get("/api/v1/companies/search?q=P&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get("/api/v1/companies/search?q=XYZ")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_search_min_length(override_db):
    response = client.get("/api/v1/companies/search?q=")
    assert response.status_code == 422
