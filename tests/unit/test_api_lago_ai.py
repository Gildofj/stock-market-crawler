import os
import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from api.deps import get_company_repo, get_crawler_db, get_lake_service, get_price_repo
from api.main import app
from core.models.models import Company, LakeNews, LakeNewsTicker, LakeRIDocument, StockPrice


# Mock Database setup
@pytest.fixture
def client(mocker):
    mocker.patch.dict(os.environ, {"API_KEY": "test"})
    mock_db = mocker.Mock()
    app.dependency_overrides[get_crawler_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_repos(mocker):
    mock_company_repo = mocker.Mock()
    mock_lake_service = mocker.Mock()
    mock_price_repo = mocker.Mock()

    app.dependency_overrides[get_company_repo] = lambda: mock_company_repo
    app.dependency_overrides[get_lake_service] = lambda: mock_lake_service
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    yield mock_company_repo, mock_lake_service, mock_price_repo


@pytest.mark.asyncio
async def test_get_news_by_company_id(client, mock_repos, mocker):
    mock_company_repo, mock_lake_service, _ = mock_repos
    company_id = uuid.uuid4()
    mock_company = Company(id=company_id, symbol="PETR4")

    mock_news = [
        LakeNews(
            id=uuid.uuid4(),
            source="InfoMoney",
            title="Petrobras bate recorde",
            url="https://infomoney.com.br/1",
            published_at=datetime.now(UTC),
            sentiment="positive"
        )
    ]
    # Simulate tickers relation
    mock_news[0].tickers = [LakeNewsTicker(ticker="PETR4")]

    mock_company_repo.get.return_value = mocker.AsyncMock(return_value=mock_company)()
    mock_lake_service.get_news_by_ticker.return_value = mocker.AsyncMock(return_value=mock_news)()

    response = client.get(f"/api/v1/news/{company_id}", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Petrobras bate recorde"
    assert data[0]["source"] == "InfoMoney"


@pytest.mark.asyncio
async def test_get_investor_relations(client, mock_repos, mocker):
    mock_company_repo, mock_lake_service, _ = mock_repos
    company_id = uuid.uuid4()
    mock_company = Company(id=company_id, symbol="VALE3")

    mock_ri = [
        LakeRIDocument(
            id=uuid.uuid4(),
            doc_id="123",
            ticker="VALE3",
            category="ITR",
            title="Informações Trimestrais",
            pdf_url="https://cvm.gov.br/doc.pdf",
            reference_date=date(2023, 9, 30)
        )
    ]

    mock_company_repo.get.return_value = mocker.AsyncMock(return_value=mock_company)()
    mock_lake_service.get_ri_documents_by_ticker.return_value = mocker.AsyncMock(return_value=mock_ri)()

    response = client.get(
        f"/api/v1/investor-relations/{company_id}", headers={"X-API-Key": "test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "ITR" in data[0]["label"]
    assert data[0]["kind"] == "cvm"


@pytest.mark.asyncio
async def test_get_quote(client, mock_repos, mocker):
    _, _, mock_price_repo = mock_repos
    company_id = uuid.uuid4()

    mock_prices = [
        StockPrice(time=datetime(2023, 10, 20), close=35.5, company_id=company_id),
        StockPrice(time=datetime(2023, 10, 19), close=34.0, company_id=company_id)
    ]

    mock_price_repo.get_history.return_value = mocker.AsyncMock(return_value=mock_prices)()

    response = client.get(f"/api/v1/prices/quote/{company_id}", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 35.5
    assert data["previous_close"] == 34.0
    assert data["change_abs"] == 1.5
    assert data["change_pct"] == pytest.approx(4.41, 0.01)
