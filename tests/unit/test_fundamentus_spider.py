import pytest
from crawler.spiders.fundamentus_spider import FundamentusSpider
from crawler.models.contract import CrawlResult

def test_fundamentus_parsing(mocker):
    # Mock RequestManager
    mock_rm = mocker.Mock()
    
    # Mock HTML response matching the spider's exact logic
    mock_html = """
    <table>
        <tr>
            <td><span class="txt">Empresa</span></td>
            <td class="data">TEST COMPANY SA</td>
        </tr>
        <tr>
            <td class="label"><span class="txt">P/L</span></td>
            <td class="data">10,50</td>
        </tr>
        <tr>
            <td class="label"><span class="txt">P/VP</span></td>
            <td class="data">1,20</td>
        </tr>
        <tr>
            <td class="label"><span class="txt">Div. Yield</span></td>
            <td class="data">5,5%</td>
        </tr>
        <tr>
            <td class="label"><span class="txt">ROE</span></td>
            <td class="data">15,0%</td>
        </tr>
    </table>
    """
    mock_resp = mocker.Mock()
    mock_resp.text = mock_html
    mock_resp.status_code = 200
    mock_rm.get.return_value = mock_resp

    spider = FundamentusSpider(request_manager=mock_rm)
    result = spider.crawl_ticker("ABCD3")

    # Verify extraction results
    assert isinstance(result, CrawlResult)
    assert result.symbol == "ABCD3"
    assert result.name == "TEST COMPANY SA"
    assert result.p_l == 10.50
    assert result.p_vp == 1.20
    assert result.dy == 5.5
    assert result.roe == 15.0
