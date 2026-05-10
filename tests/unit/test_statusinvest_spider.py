from crawler.models.contract import CrawlResult
from crawler.spiders.statusinvest_spider import StatusInvestSpider


def test_statusinvest_mapping(mocker):
    # Mock RequestManager
    mock_rm = mocker.Mock()

    # Mock JSON response from API
    mock_json = [
        {
            "ticker": "ABCD3",
            "companyName": "TEST COMPANY SA",
            "p_L": 10.50,
            "p_VP": 1.20,
            "dy": 5.5,
            "roe": 15.0,
            "roic": 12.5,
            "ev_Ebitda": 7.20,
            "margemLiquida": 20.0,
            "dividaliquidaEbitda": 1.50,
            "receitas_cagr5": 8.5,
            "lucros_cagr5": 10.0,
            "dividaLiquidaPatrimonioLiquido": 0.5,
            "valorMercado": 1000000,
            "lpa": 1.5,
        }
    ]
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = mock_json
    mock_resp.status_code = 200
    mock_rm.get.return_value = mock_resp

    spider = StatusInvestSpider(request_manager=mock_rm)
    result = spider.crawl_ticker("ABCD3")

    # Verify mapping results
    assert isinstance(result, CrawlResult)
    assert result.symbol == "ABCD3"
    assert result.name == "TEST COMPANY SA"
    assert result.p_l == 10.50
    assert result.p_vp == 1.20
    assert result.dy == 5.5
    assert result.roe == 15.0
    assert result.roic == 12.5
    assert result.ev_ebitda == 7.20
    assert result.net_margin == 20.0
    assert result.liquid_debt_ebitda == 1.50
    assert result.cagr_revenue_5y == 8.5
    assert result.cagr_profit_5y == 10.0
    assert result.market_cap == 1000000
    assert result.eps == 1.5
