import asyncio
import math
import uuid

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

    def __init__(
        self,
        db: Session,
        request_manager: RequestManager | None = None,
        spiders: dict | None = None,
    ):
        """
        Initializes the CrawlerEngine with necessary dependencies.

        Args:
            db: SQLAlchemy session for database operations.
            request_manager: Optional manager for HTTP requests and rate limiting.
            spiders: Optional dictionary of pre-initialized spiders.
        """
        self.data_service = DataService(db)
        self.request_manager = request_manager or RequestManager()

        # Initialize spiders with shared request manager for unified rate limiting
        spiders = spiders or {}
        self.b3_spider = spiders.get("b3") or B3Spider()
        self.fundamentus_spider = spiders.get("fundamentus") or FundamentusSpider(
            self.request_manager
        )
        self.status_spider = spiders.get("status") or StatusInvestSpider(
            self.request_manager
        )

    async def run_batch_async(self, symbols: list[str]) -> list[CrawlResult]:
        """
        Executes the enrichment chain for a batch of stock symbols efficiently.
        """
        logger.info(f"Engine: Starting batch enrichment for {len(symbols)} tickers")

        # 1. Batch Primary Source: B3 (yfinance batch)
        # This gets all prices in one/two network calls instead of 100s
        results_dict = await self.b3_spider.crawl_batch_async(symbols)
        
        # 2. Sequential Fallback and Persistence (with shared caches)
        final_results = []
        for symbol in symbols:
            result = results_dict.get(symbol) or CrawlResult(symbol=symbol)
            
            # Check if company exists to avoid redundant metadata scraping
            company_exists = await asyncio.to_thread(
                self.data_service.get_company_by_symbol, symbol
            )

            # First Fallback: Fundamentus (only if really needed)
            if not result.is_complete():
                await self.fundamentus_spider.enrich_async(result)

            # Second Fallback: StatusInvest (Conditional metadata enrichment)
            if not result.is_complete() or not company_exists:
                # enrich_metadata=True only for new companies
                await self.status_spider.enrich_async(
                    result, enrich_metadata=not company_exists
                )

            self._calculate_advanced_metrics(result)

            # Persistence
            await asyncio.to_thread(self._save_to_db, result)
            final_results.append(result)

        return final_results

    async def run_for_ticker_async(self, symbol: str) -> CrawlResult:
        """
        Executes the full enrichment chain for a single stock symbol asynchronously.
        """
        logger.info(f"Engine: Starting async enrichment chain for {symbol}")

        # 1. Primary Source: B3 (yfinance wrapped in thread)
        result = await self.b3_spider.crawl_ticker_async(symbol)

        # 2. First Fallback: Fundamentus
        if not result.is_complete():
            logger.debug(f"Engine: Result incomplete for {symbol}. Fallback to Fundamentus.")
            await self.fundamentus_spider.enrich_async(result)

        # 3. Second Fallback: StatusInvest
        if not result.is_complete():
            logger.debug(f"Engine: Result still incomplete for {symbol}. Fallback to StatusInvest.")
            await self.status_spider.enrich_async(result)

        self._calculate_advanced_metrics(result)

        # Persistence is usually synchronous (SQLAlchemy)
        await asyncio.to_thread(self._save_to_db, result)

        return result

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
        result = self.b3_spider.crawl_ticker(symbol)

        # 2. First Fallback: Fundamentus
        if not result.is_complete():
            logger.warning(
                f"Engine: Result incomplete for {symbol} after B3 crawl. "
                "Triggering fallback to Fundamentus."
            )
            self.fundamentus_spider.enrich(result)

        # 3. Second Fallback: StatusInvest
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

        # 4. Advanced Metrics Calculation
        self._calculate_advanced_metrics(result)

        # 5. Persistence
        self._save_to_db(result)

        return result

    async def shutdown(self):
        """Closes resources."""
        await self.request_manager.close()

    def _calculate_advanced_metrics(self, result: CrawlResult) -> None:
        """
        Calculates Fair Value valuations (Graham, Bazin) and a composite Quality Score.
        """
        # Get current price from the latest entry in prices
        current_price = result.prices[-1].close if result.prices else None

        # 1. Graham Valuation: sqrt(22.5 * LPA * VPA)
        # VPA = Price / P/VP
        if result.eps and result.p_vp and result.p_vp > 0 and current_price:
            vpa = current_price / result.p_vp
            # Graham formula only works for positive EPS and VPA
            if result.eps > 0 and vpa > 0:
                result.valuation_graham = math.sqrt(22.5 * result.eps * vpa)

        # 2. Bazin Valuation: (Dividend / 0.06)
        # Dividend = (DY% / 100) * Price
        if result.dy and result.dy > 0 and current_price:
            annual_dividend = (result.dy / 100) * current_price
            result.valuation_bazin = annual_dividend / 0.06

        # 3. Quality Score (0-100)
        score = 0
        metrics_count = 0

        metric_rules = [
            (result.roe, 15, 10),
            (result.roic, 12, 8),
            (result.net_margin, 10, 5),
            (result.cagr_revenue_5y, 5, 0),
        ]

        for val, high, mid in metric_rules:
            if val is not None:
                if val > high:
                    score += 20
                elif val > mid:
                    score += 10
                metrics_count += 1

        # Debt/EBITDA is inverse
        if result.liquid_debt_ebitda is not None:
            if result.liquid_debt_ebitda < 2.0:
                score += 20
            elif result.liquid_debt_ebitda < 3.5:
                score += 10
            metrics_count += 1

        if metrics_count > 0:
            result.quality_score = score

    def _save_to_db(self, result: CrawlResult) -> None:
        """
        Maps CrawlResult back to domain schemas and persists data using DataService.
        """
        company_schema = CompanySchema(
            symbol=result.symbol,
            name=result.name or result.symbol,
            sector=result.sector,
            sub_sector=result.sub_sector,
            segment=result.segment,
            logo_url=result.logo_url,
            website=result.website,
            is_active=result.is_active,
        )
        company = self.data_service.get_or_create_company(company_schema)

        # Cast Column[UUID] to uuid.UUID for type checker
        company_id = uuid.UUID(str(company.id))

        if result.prices:
            self.data_service.save_prices(company_id, result.prices)

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
            eps=result.eps,
            valuation_graham=result.valuation_graham,
            valuation_bazin=result.valuation_bazin,
            quality_score=result.quality_score,
        )
        self.data_service.save_fundamentals(company_id, fundamental_schema)
        logger.debug(f"Engine: Persistence completed for {result.symbol}")
