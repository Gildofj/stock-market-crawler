import asyncio
import uuid

from loguru import logger
from sqlalchemy.orm import Session

from ..models.contract import CrawlResult
from ..models.schemas import CompanySchema, FundamentalSchema
from ..repositories import (
    CompanyRepository,
    FundamentalRepository,
    PriceRepository,
)
from ..services.financial_calculator import bazin_fair_value, graham_fair_value
from ..services.reconciliation_service import ReconciliationService
from ..services.request_manager import RequestManager
from ..spiders.b3_spider import B3Spider
from ..spiders.cvm_spider import CVMSpider


class CrawlerEngine:
    """Orchestrates the per-ticker fundamentals pipeline.

    The engine talks to two clean-room data sources:

    1. ``B3Spider`` (yfinance) — historical prices, current quote, market cap
       and shares outstanding. Prices are facts (Lei 9.610/98 Art. 8º) and
       carry no copyright exposure.
    2. ``CVMSpider`` — raw standardized statements from CVM Dados Abertos.
       Indicators (P/L, P/VP, ROE, ROIC, EV/EBITDA, margins, debt ratios,
       Graham, Bazin) are computed locally from these line items using
       :mod:`crawler.services.financial_calculator`, so we never depend on
       proprietary methodologies maintained by third-party platforms.
    """

    def __init__(
        self,
        db: Session,
        request_manager: RequestManager | None = None,
        spiders: dict | None = None,
    ):
        self.company_repo = CompanyRepository(db)
        self.price_repo = PriceRepository(db)
        self.fundamental_repo = FundamentalRepository(db)
        self.reconciliation_service = ReconciliationService(db)
        self.request_manager = request_manager or RequestManager()

        spiders = spiders or {}
        self.b3_spider = spiders.get("b3") or B3Spider()
        self.cvm_spider = spiders.get("cvm") or CVMSpider()

    async def run_batch_async(self, symbols: list[str]) -> list[CrawlResult]:
        """Run the price + fundamentals pipeline across a batch of tickers."""
        logger.info(f"Engine: Starting batch enrichment for {len(symbols)} tickers")

        results_dict = await self.b3_spider.crawl_batch_async(symbols)

        final_results = []
        for symbol in symbols:
            result = results_dict.get(symbol) or CrawlResult(symbol=symbol)

            await self.cvm_spider.enrich_async(result)
            self._calculate_advanced_metrics(result)

            await asyncio.to_thread(self._save_to_db, result)
            final_results.append(result)

        return final_results

    async def run_for_ticker_async(self, symbol: str) -> CrawlResult:
        logger.info(f"Engine: Starting async enrichment chain for {symbol}")
        result = await self.b3_spider.crawl_ticker_async(symbol)
        await self.cvm_spider.enrich_async(result)
        self._calculate_advanced_metrics(result)
        await asyncio.to_thread(self._save_to_db, result)
        return result

    def run_for_ticker(self, symbol: str) -> CrawlResult:
        logger.info(f"Engine: Starting enrichment chain for {symbol}")
        result = self.b3_spider.crawl_ticker(symbol)
        self.cvm_spider.enrich(result)
        self._calculate_advanced_metrics(result)
        self._save_to_db(result)
        logger.success(f"Engine: completed enrichment for {symbol}")
        return result

    async def shutdown(self):
        await self.request_manager.close()

    def _calculate_advanced_metrics(self, result: CrawlResult) -> None:
        """Compute Graham / Bazin fair-value targets and a quality score."""
        current_price = result.prices[-1].close if result.prices else None
        bvps = (
            current_price / result.p_vp
            if result.p_vp and result.p_vp > 0 and current_price
            else None
        )

        result.valuation_graham = graham_fair_value(result.eps, bvps)

        annual_dividend = (
            (result.dy / 100) * current_price
            if result.dy and result.dy > 0 and current_price
            else None
        )
        result.valuation_bazin = bazin_fair_value(annual_dividend)

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

        if result.liquid_debt_ebitda is not None:
            if result.liquid_debt_ebitda < 2.0:
                score += 20
            elif result.liquid_debt_ebitda < 3.5:
                score += 10
            metrics_count += 1

        if metrics_count > 0:
            result.quality_score = score

    def _save_to_db(self, result: CrawlResult) -> None:
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
        company = self.company_repo.get_or_create(company_schema)
        company_id = uuid.UUID(str(company.id))

        if result.prices:
            self.price_repo.save_bulk(company_id, result.prices)

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
        self.fundamental_repo.save(company_id, fundamental_schema)

        # Reconciliation rows — observational only. Must never break the
        # crawl: any failure is logged and swallowed.
        try:
            self.reconciliation_service.emit(company_id, result)
        except Exception as exc:
            logger.warning(f"reconciliation failed for {result.symbol}: {exc}")

        logger.debug(f"Engine: Persistence completed for {result.symbol}")
