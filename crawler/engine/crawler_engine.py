
from loguru import logger
from sqlalchemy.orm import Session

from ..models.contract import CrawlResult
from ..models.schemas import CompanySchema, FundamentalSchema
from ..services.data_service import DataService
from ..services.request_manager import RequestManager
from ..spiders.b3_spider import B3Spider
from ..spiders.fundamentus_spider import FundamentusSpider
from ..spiders.statusinvest_spider import StatusInvestSpider


class CrawlerEngine:
    """
    Main orchestration engine for the stock market crawler.

    The engine implements an enrichment chain pattern:
    1. Primary crawl using B3/yfinance (fast, reliable for prices).
    2. Fallback to Fundamentus if core fundamental indicators are missing.
    3. Final fallback to StatusInvest for missing data.

    This ensures maximum data coverage and resilience against single-source failures.
    """

    def __init__(self, db: Session, request_manager: RequestManager | None = None):
        """
        Initializes the CrawlerEngine with necessary dependencies.

        Args:
            db: SQLAlchemy session for database operations.
            request_manager: Optional manager for HTTP requests and rate limiting.
        """
        self.data_service = DataService(db)
        self.request_manager = request_manager or RequestManager()

        # Initialize spiders with shared request manager for unified rate limiting
        self.b3_spider = B3Spider()
        self.fundamentus_spider = FundamentusSpider(self.request_manager)
        self.status_spider = StatusInvestSpider(self.request_manager)

    def run_for_ticker(self, symbol: str) -> CrawlResult:
        """
        Executes the full enrichment chain for a single stock symbol.

        The process follows a prioritized sequence of scrapers, only triggering
        fallbacks if the current result set is considered incomplete.

        Args:
            symbol: The stock ticker symbol to process.

        Returns:
            CrawlResult: The final enriched dataset for the symbol.
        """
        logger.info(f"Engine: Starting enrichment chain for {symbol}")

        # 1. Primary Source: B3 (yfinance)
        # B3 usually provides reliable prices and basic company info.
        result = self.b3_spider.crawl_ticker(symbol)

        # 2. First Fallback: Fundamentus
        # Triggered if essential fundamental metrics (P/L, ROE, etc.) are missing.
        if not result.is_complete():
            logger.warning(
                f"Engine: Result incomplete for {symbol} after B3 crawl. "
                "Triggering fallback to Fundamentus."
            )
            self.fundamentus_spider.enrich(result)

        # 3. Second Fallback: StatusInvest
        # Final attempt to fill remaining gaps.
        if not result.is_complete():
            logger.warning(
                f"Engine: Result still incomplete for {symbol} after Fundamentus. "
                "Triggering fallback to StatusInvest."
            )
            self.status_spider.enrich(result)

        # Final status check
        if not result.is_complete():
            logger.error(f"Engine: Enrichment chain finished with partial data for {symbol}")
        else:
            logger.success(f"Engine: Successfully completed enrichment for {symbol}")

        # 4. Persistence
        # Map the unified CrawlResult to domain schemas and save to DB.
        self._save_to_db(result)

        return result

    def _save_to_db(self, result: CrawlResult) -> None:
        """
        Maps CrawlResult back to domain schemas and persists data using DataService.

        Args:
            result: The enriched data container.
        """
        # Map Company metadata
        company_schema = CompanySchema(
            symbol=result.symbol,
            name=result.name,
            sector=result.sector,
            sub_sector=result.sub_sector,
            segment=result.segment,
            logo_url=result.logo_url,
            is_active=result.is_active
        )
        company = self.data_service.get_or_create_company(company_schema)

        # Map and save historical prices
        if result.prices:
            self.data_service.save_prices(company.id, result.prices)

        # Map and save fundamental indicators
        fundamental_schema = FundamentalSchema(
            p_l=result.p_l,
            p_vp=result.p_vp,
            ev_ebitda=result.ev_ebitda,
            roe=result.roe,
            roic=result.roic,
            net_margin=result.net_margin,
            dy=result.dy,
            liquid_debt_ebitda=result.liquid_debt_ebitda,
            cagr_revenue_5y=result.cagr_revenue_5y,
            cagr_profit_5y=result.cagr_profit_5y,
            debt_to_equity=result.debt_to_equity,
            market_cap=result.market_cap,
            eps=result.eps
        )
        self.data_service.save_fundamentals(company.id, fundamental_schema)

        logger.debug(f"Engine: Persistence completed for {result.symbol}")
