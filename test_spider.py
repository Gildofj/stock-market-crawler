import asyncio
from crawler.spiders.cvm_spider import CVMSpider
from crawler.services.cvm_dataset_service import CVMDatasetService
from crawler.models.contract import CrawlResult

async def main():
    service = CVMDatasetService()
    spider = CVMSpider(service)
    
    result = CrawlResult(symbol="PETR4")
    # Simulate B3 spider price fetching
    from core.models.schemas import StockPriceSchema
    from datetime import datetime, time, timezone
    result.prices = [StockPriceSchema(date=datetime.now().date(), time=datetime.now(timezone.utc), open=35.0, high=36.0, low=34.0, close=35.5, volume=10000000, company_id="123e4567-e89b-12d3-a456-426614174000")]
    result.shares_outstanding = 13044000000.0 # adding shares outstanding!
    await spider.enrich(result)
    
    print("Result P/L:", result.p_l)
    print("Result DY:", result.dy)
    print("Result EPS:", result.eps)
    print("Result ROE:", result.roe)
    print("Result ROIC:", result.roic)
    print("Result Quality Score:", result.quality_score)
    print("Result Bazin:", result.valuation_bazin)
    print("Result Graham:", result.valuation_graham)

asyncio.run(main())
