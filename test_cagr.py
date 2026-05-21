import asyncio
import logging

from crawler.services.cvm_dataset_service import CVMDatasetService
from crawler.spiders.cvm_spider import CVMSpider

logging.basicConfig(level=logging.DEBUG)


async def main():
    service = CVMDatasetService()
    spider = CVMSpider(service)

    cvm_code = spider.get_cvm_code("WEGE3")
    if not cvm_code:
        print("Could not find WEGE3")
        return

    print(f"WEGE3 CVM Code: {cvm_code}")

    from crawler.spiders.cvm_spider import _NET_INCOME, _REVENUE

    cagr_rev = spider._cagr_for(cvm_code, "DRE", _REVENUE, years=5)
    cagr_prof = spider._cagr_for(cvm_code, "DRE", _NET_INCOME, years=5)

    print(f"CAGR Revenue 5y: {cagr_rev}")
    print(f"CAGR Profit 5y: {cagr_prof}")

    # Let's see year by year
    for year in range(2018, 2026):
        val = spider._annual_value(cvm_code, year, _REVENUE)
        print(f"Revenue {year}: {val}")


if __name__ == "__main__":
    asyncio.run(main())
