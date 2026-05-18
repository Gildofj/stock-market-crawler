import uuid
import os
import pytest
from datetime import datetime, date, UTC
from fastapi.testclient import TestClient
from sqlalchemy import create_mock_engine
from sqlalchemy.orm import sessionmaker
from api.main import app
from api.deps import get_crawler_db
from crawler.models.models import Company, LakeNews, LakeNewsTicker, LakeRIDocument, StockPrice

# Mock Database setup
@pytest.fixture
def client(mocker):
    mocker.patch.dict(os.environ, {"API_KEY": "test"})
    mock_db = mocker.Mock()
    app.dependency_overrides[get_crawler_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_get_news_by_company_id(client, mocker):
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

    client.app.dependency_overrides[get_crawler_db]().query.return_value.filter.return_value.first.return_value = mock_company
    client.app.dependency_overrides[get_crawler_db]().query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_news

    response = client.get(f"/api/v1/news/{company_id}", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Petrobras bate recorde"
    assert data[0]["source"] == "InfoMoney"

def test_get_investor_relations(client, mocker):
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

    client.app.dependency_overrides[get_crawler_db]().query.return_value.filter.return_value.first.return_value = mock_company
    client.app.dependency_overrides[get_crawler_db]().query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_ri

    response = client.get(f"/api/v1/investor-relations/{company_id}", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "ITR" in data[0]["label"]
    assert data[0]["kind"] == "cvm"

def test_get_quote(client, mocker):
    company_id = uuid.uuid4()
    
    mock_prices = [
        StockPrice(time=datetime(2023, 10, 20), close=35.5, company_id=company_id),
        StockPrice(time=datetime(2023, 10, 19), close=34.0, company_id=company_id)
    ]

    client.app.dependency_overrides[get_crawler_db]().query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_prices

    response = client.get(f"/api/v1/prices/quote/{company_id}", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 35.5
    assert data["previous_close"] == 34.0
    assert data["change_abs"] == 1.5
    assert data["change_pct"] == pytest.approx(4.41, 0.01)
