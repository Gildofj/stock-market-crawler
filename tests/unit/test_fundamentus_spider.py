from crawler.spiders.fundamentus_spider import FundamentusSpider


def test_fundamentus_parsing(mocker):
    # Mock data_service
    mock_ds = mocker.Mock()
    mock_company = mocker.Mock()
    mock_company.id = 1
    mock_ds.get_or_create_company.return_value = mock_company

    spider = FundamentusSpider(mock_ds)

    # Mock HTML response from Fundamentus
    mock_html = """
    <html>
        <table>
            <tr><td>Empresa</td><td><td>TEST COMPANY SA</td></tr>
            <tr><td><span string="P/L">P/L</span></td><td><td>10,50</td></tr>
            <tr><td><span string="P/VP">P/VP</span></td><td><td>1,20</td></tr>
            <tr><td><span string="Div. Yield">Div. Yield</span></td><td><td>5,5%</td></tr>
            <tr><td><span string="ROE">ROE</span></td><td><td>15,0%</td></tr>
        </table>
    </html>
    """

    # We need to mock RequestManager.get to return this HTML
    mock_resp = mocker.Mock()
    mock_resp.text = mock_html
    mock_resp.status_code = 200
    mocker.patch("crawler.services.request_manager.RequestManager.get", return_value=mock_resp)
    
    # Also mock logo service to avoid extra requests
    mocker.patch("crawler.services.logo_service.LogoService.update_logo_if_missing")

    # Note: The spider uses a slightly more complex soup.find('span', string='P/L')
    # Let's adjust the test to match the spider's logic or vice-versa if needed.
    # The current spider logic: soup.find('span', string=label).parent.find_next_sibling('td').text

    # Redoing mock_html to match EXACT logic of the spider
    mock_html_strict = """
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
    mock_resp.text = mock_html_strict

    spider.crawl_ticker("ABCD3")

    # Verify data service calls
    assert mock_ds.save_fundamentals.called
    args, _ = mock_ds.save_fundamentals.call_args
    fundamental_data = args[1]

    assert fundamental_data.p_l == 10.50
    assert fundamental_data.p_vp == 1.20
    assert fundamental_data.dy == 5.5
    assert fundamental_data.roe == 15.0
