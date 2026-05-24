import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.schemas import CompanySchema, FundamentalSchema
from core.repositories import (
    CompanyRepository,
    FundamentalRepository,
    PriceRepository,
)
from core.services.financial_calculator import bazin_fair_value, graham_fair_value

from ..models.contract import CrawlResult
from ..services.logo_service import LogoService
from ..services.metadata_resolver import MetadataResolver
from ..services.reconciliation_service import ReconciliationService
from ..services.request_manager import RequestManager
from ..spiders.b3_spider import B3Spider
from ..spiders.bdr_spider import BDRSpider
from ..spiders.cvm_spider import CVMSpider
from ..spiders.fii_spider import FIISpider


class CrawlerEngine:
    def __init__(
        self,
        db: AsyncSession,
        request_manager: RequestManager | None = None,
        spiders: dict | None = None,
    ):
        self.company_repo = CompanyRepository(db)
        self.price_repo = PriceRepository(db)
        self.fundamental_repo = FundamentalRepository(db)
        self.reconciliation_service = ReconciliationService(db)
        if request_manager is None:
            from core.config import settings

            proxies = []
            if settings.CRAWLER_HTTP_PROXY:
                proxies.append(settings.CRAWLER_HTTP_PROXY)
            if settings.CRAWLER_HTTPS_PROXY:
                proxies.append(settings.CRAWLER_HTTPS_PROXY)
            self.request_manager = RequestManager(proxies=proxies if proxies else None)
        else:
            self.request_manager = request_manager

        spiders = spiders or {}
        self.b3_spider = spiders.get("b3") or B3Spider()
        self.cvm_spider = spiders.get("cvm") or CVMSpider()
        self.fii_spider = spiders.get("fii") or FIISpider()
        self.bdr_spider = spiders.get("bdr") or BDRSpider()
        self.metadata_resolver = MetadataResolver(
            self.cvm_spider,
            LogoService(self.company_repo, request_manager=self.request_manager),
        )

    async def run_batch_async(self, symbols: list[str]) -> list[CrawlResult]:
        logger.info(f"Engine: Starting batch enrichment for {len(symbols)} tickers")

        results_dict = await self.b3_spider.crawl_batch_async(symbols)

        final_results = []
        for symbol in symbols:
            result = results_dict.get(symbol) or CrawlResult(symbol=symbol)

            await self.cvm_spider.enrich(result)
            await self.metadata_resolver.apply(result)
            self._calculate_advanced_metrics(result)

            await self._save_to_db(result)
            final_results.append(result)

        return final_results

    async def run_for_ticker_async(self, symbol: str) -> CrawlResult:
        logger.info(f"Engine: Starting async enrichment chain for {symbol}")
        taxonomy = await self.company_repo.get_taxonomy(symbol) or {}
        asset_type = (taxonomy.get("asset_type") or _infer_asset_type(symbol)).upper()

        result = await self.b3_spider.crawl_ticker(symbol)
        await self._enrich_by_asset_type(result, asset_type, taxonomy)
        await self.metadata_resolver.apply(result)
        self._calculate_advanced_metrics(result)
        result.provenance.setdefault("asset_type", asset_type)
        await self._save_to_db(result, asset_type=asset_type)
        return result

    async def _enrich_by_asset_type(
        self, result: CrawlResult, asset_type: str, taxonomy: dict
    ) -> None:
        if asset_type == "FII":
            await self.fii_spider.enrich(result)
            return
        if asset_type == "BDR":
            await self.bdr_spider.enrich(
                result,
                underlying=taxonomy.get("underlying_ticker"),
            )
            return
        # Default path (EQUITY, UNIT, ETF and anything unrecognised): seed the
        # CVM spider with any cached cd_cvm so it skips the Brapi roundtrip.
        cd_cvm = taxonomy.get("cd_cvm")
        if cd_cvm:
            self.cvm_spider.seed_ticker_index({symbol_key(result.symbol): cd_cvm})
        await self.cvm_spider.enrich(result)

    async def run_for_ticker(self, symbol: str) -> CrawlResult:
        logger.info(f"Engine: Starting enrichment chain for {symbol}")
        result = await self.run_for_ticker_async(symbol)
        logger.success(f"Engine: completed enrichment for {symbol}")
        return result

    async def shutdown(self):
        await self.request_manager.close()

    def _calculate_advanced_metrics(self, result: CrawlResult) -> None:
        current_price = result.prices[-1].close if result.prices else None
        bvps = (
            current_price / result.p_vp
            if result.p_vp and result.p_vp > 0 and current_price
            else None
        )

        if result.valuation_graham is None:
            result.valuation_graham = graham_fair_value(result.eps, bvps)

        if result.valuation_bazin is None:
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

    async def _ensure_source_ids(self) -> None:
        if hasattr(self, "_source_ids") and self._source_ids:
            return

        from sqlalchemy import select

        from core.models.models import DataSource

        stmt = select(DataSource.slug, DataSource.id)
        res = await self.company_repo.db.execute(stmt)
        self._source_ids = {row[0]: row[1] for row in res.all()}

    _CORE_INDICATOR_FIELDS: tuple[str, ...] = (
        "p_l",
        "p_vp",
        "ev_ebitda",
        "roe",
        "roic",
        "net_margin",
        "liquid_debt_ebitda",
        "debt_to_equity",
        "market_cap",
        "eps",
    )

    async def _save_to_db(self, result: CrawlResult, asset_type: str = "EQUITY") -> None:
        await self._ensure_source_ids()

        result.primary_source_id = self._source_ids.get("cvm")
        result.contributing_sources = [
            slug for slug in ("cvm", "yfinance") if self._source_ids.get(slug)
        ]

        company_schema = CompanySchema(
            symbol=result.symbol,
            name=result.name or result.symbol,
            sector=result.sector,
            sub_sector=result.sub_sector,
            segment=result.segment,
            logo_url=result.logo_url,
            website=result.website,
            is_active=result.is_active,
            asset_type=asset_type,
        )
        company = await self.company_repo.get_or_create(company_schema)
        company_id = uuid.UUID(str(company.id))

        if result.prices:
            yfinance_id = self._source_ids.get("yfinance")
            for price in result.prices:
                price.source_id = yfinance_id
            await self.price_repo.save_bulk(company_id, result.prices)

        populated = [f for f in self._CORE_INDICATOR_FIELDS if getattr(result, f) is not None]
        if not populated:
            logger.error(
                "Engine: skipping fundamentals row for "
                f"ticker={result.symbol} reason=no_fundamentals_computed "
                f"asset_type={asset_type} "
                f"indicators_populated=0 indicators_total={len(self._CORE_INDICATOR_FIELDS)}"
            )
        else:
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
                asset_type=asset_type,
                primary_source_id=result.primary_source_id,
                contributing_sources=result.contributing_sources,
                provenance=result.provenance,
            )
            await self.fundamental_repo.save(company_id, fundamental_schema)
            logger.info(
                f"Engine: fundamentals persisted ticker={result.symbol} "
                f"asset_type={asset_type} "
                f"indicators_populated={len(populated)} "
                f"indicators_total={len(self._CORE_INDICATOR_FIELDS)}"
            )

        # Reconciliation only makes sense for EQUITY (compares CVM vs yfinance).
        if asset_type == "EQUITY":
            try:
                await self.reconciliation_service.emit(company_id, result)
            except Exception as exc:
                logger.warning(f"reconciliation failed for {result.symbol}: {exc}")


def symbol_key(symbol: str) -> str:
    return symbol.upper().replace(".SA", "")


def _infer_asset_type(symbol: str) -> str:
    """Fallback when companies.asset_type is null (cold start before
    refresh_universe runs). Mirrors brapi_client._normalise_asset_type.
    """
    cleaned = symbol_key(symbol).rstrip("F")
    if cleaned.endswith("11"):
        return "FII"
    if cleaned.endswith(("32", "33", "34", "35")):
        return "BDR"
    return "EQUITY"
