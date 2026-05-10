from loguru import logger

from crawler.services.data_service import DataService
from crawler.services.database import session_local
from crawler.services.etl_service import ETLService
from crawler.services.request_manager import RequestManager
from crawler.spiders.b3_spider import B3Spider
from crawler.spiders.fundamentus_spider import FundamentusSpider
from crawler.spiders.macro_spider import MacroSpider
from crawler.spiders.statusinvest_spider import StatusInvestSpider

request_manager = RequestManager()  # Can add proxy list here


def crawl_ticker_task(symbol: str):
    """Sync function to crawl a single ticker from multiple sources."""
    # Bind the symbol to the logger for tracing
    task_logger = logger.bind(ticker=symbol)

    task_logger.info(f"Starting multi-source crawl for {symbol}")
    db = session_local()
    try:
        data_service = DataService(db)
        etl_service = ETLService(db)

        # 1. Price Data & Initial Fundamentals (yfinance)
        yfinance_spider = B3Spider(data_service)
        yfinance_spider.crawl_ticker(symbol)

        # 2. Advanced Fundamentals (Scraping Fundamentus)
        fundamentus_spider = FundamentusSpider(data_service)
        fundamentus_spider.crawl_ticker(symbol)

        # 3. Quality Check & Refinement (Scraping StatusInvest)
        status_spider = StatusInvestSpider(data_service)
        status_spider.crawl_ticker(symbol)

        # 4. ETL Pipeline (Generate ML Features)
        company = data_service.get_company_by_symbol(symbol)
        if company:
            etl_service.generate_features(company.id)
            task_logger.info(f"Ticker {symbol} completed successfully.")

    except Exception as e:
        task_logger.error(f"Task for {symbol} failed: {e}")
    finally:
        db.close()


def crawl_macro_data_task():
    """Sync task to fetch macro indicators."""
    logger.info("Starting macro data collection...")
    db = session_local()
    try:
        data_service = DataService(db)
        macro_spider = MacroSpider(data_service)
        macro_spider.crawl_macro_indicators()
        logger.info("Macro data collection completed.")
    except Exception as e:
        logger.error(f"Macro task failed: {e}")
    finally:
        db.close()
