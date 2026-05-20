from crawler.spiders.macro_spider import MacroSpider


def test_macro_spider_404_handling(mocker):
    # Mock RequestManager
    mock_rm = mocker.Mock()

    # Mock responses
    mock_resp_404 = mocker.Mock()
    mock_resp_404.status_code = 404

    # We want both SELIC and IPCA to return 404 to test the warning logging
    mock_rm.get.return_value = mock_resp_404

    spider = MacroSpider(request_manager=mock_rm)

    # This should not raise an exception even if it gets 404s
    spider.crawl_macro_indicators()

    # Verify both URLs were called
    assert mock_rm.get.call_count == 2


def test_macro_spider_success(mocker):
    # Mock RequestManager
    mock_rm = mocker.Mock()

    # Mock responses
    mock_resp_200 = mocker.Mock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = [{"data": "01/01/2026", "valor": "10.50"}]
    mock_resp_200.headers = {"Content-Type": "application/json"}

    mock_rm.get.return_value = mock_resp_200

    spider = MacroSpider(request_manager=mock_rm)

    # Should complete without error
    spider.crawl_macro_indicators()

    assert mock_rm.get.call_count == 2
