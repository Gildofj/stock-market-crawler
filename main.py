import os
import socket
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def patch_database_url_for_ipv4():
    """
    Force IPv4 for Supabase/Postgres connections by injecting 'hostaddr'.
    This bypasses IPv6 resolution issues in GitHub Actions while maintaining SSL.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url or "supabase" not in db_url:
        return
    
    try:
        parsed = urlparse(db_url)
        hostname = parsed.hostname
        if not hostname:
            return
            
        # Resolve hostname to IPv4 manually
        # This uses the system's IPv4 resolution which is more reliable in GHA
        addr_info = socket.getaddrinfo(hostname, parsed.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
        if not addr_info:
            return
            
        ipv4 = addr_info[0][4][0]
        
        # Inject hostaddr into query parameters
        query = dict(parse_qsl(parsed.query))
        query['hostaddr'] = ipv4
        
        new_query = urlencode(query)
        new_url = urlunparse(parsed._replace(query=new_query))
        
        # Overwrite env var so settings.database_url picks it up
        os.environ["DATABASE_URL"] = new_url
        print(f"DEBUG: FORCING IPv4 for {hostname} -> {ipv4}")
    except Exception as e:
        print(f"DEBUG: Failed to patch DATABASE_URL for IPv4: {e}")

# Apply patch before any other imports that might initialize the DB engine
patch_database_url_for_ipv4()

import time
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from crawler.services.ticker_service import TickerService
from crawler.tasks import crawl_macro_data_task, crawl_ticker_task

def main():
    logger.info("Starting stock-market-crawler (GitHub Actions Mode)...")

    # 1. Fetch Macro Data (Once per run)
    try:
        crawl_macro_data_task()
    except Exception as e:
        logger.error(f"Failed to fetch macro data: {e}")

    # 2. Fetch all Tickers
    ticker_service = TickerService()
    tickers = ticker_service.get_all_tickers()

    if not tickers:
        logger.error("No tickers found. Aborting.")
        return

    # Use ThreadPoolExecutor to process tickers in parallel.
    # max_workers=5 is a safe limit for Supabase Free Tier (which has a connection limit).
    # This also prevents the GitHub Action from being throttled by external APIs.
    MAX_WORKERS = 5
    logger.info(f"Processing {len(tickers)} companies using {MAX_WORKERS} parallel workers...")

    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # map handles the distribution of tickers to the pool
        executor.map(crawl_ticker_task, tickers)

    duration = time.time() - start_time
    logger.info(f"Crawling completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
