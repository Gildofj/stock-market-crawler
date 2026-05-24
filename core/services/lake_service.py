import uuid
from datetime import UTC, date, datetime, timedelta

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from core.exceptions import DatabaseError
from core.models.models import LakeInsightCache, LakeNews, LakeNewsTicker, LakeRIDocument
from core.models.schemas import (
    LakeInsightSchema,
    LakeNewsSchema,
    LakeRIDocumentInternalSchema,
)
from core.services.source_registry import SourceNotFoundError, get_source_registry


async def _resolve_source_id(slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    try:
        source = await get_source_registry().get(slug)
        return uuid.UUID(source.id)
    except SourceNotFoundError:
        logger.warning(f"LakeService: unknown source slug {slug!r}; persisting without FK.")
        return None


class LakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_news(self, payload: LakeNewsSchema) -> LakeNews:
        # selectinload is mandatory: _sync_tickers iterates news.tickers, and async
        # SQLAlchemy forbids lazy loading outside greenlet IO context.
        stmt = (
            select(LakeNews)
            .options(selectinload(LakeNews.tickers))
            .filter(LakeNews.url_hash == payload.url_hash)
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        source_id = await _resolve_source_id(payload.source)

        if existing:
            existing.title = payload.title
            existing.summary = payload.summary
            existing.sentiment = payload.sentiment
            existing.published_at = payload.published_at
            if source_id is not None and existing.source_id is None:
                existing.source_id = source_id
            await self._sync_tickers(existing, payload.tickers)
            try:
                await self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                await self.db.rollback()
                logger.error(f"Update news failed for {payload.url}: {exc}")
                raise DatabaseError("Failed to update news") from exc

        news = LakeNews(
            source=payload.source,
            source_id=source_id,
            title=payload.title,
            summary=payload.summary,
            url=payload.url,
            url_hash=payload.url_hash,
            sentiment=payload.sentiment,
            published_at=payload.published_at,
        )
        for ticker in set(payload.tickers):
            news.tickers.append(LakeNewsTicker(ticker=ticker))
        self.db.add(news)
        try:
            await self.db.commit()
            await self.db.refresh(news)
            return news
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"Insert news failed for {payload.url}: {exc}")
            raise DatabaseError("Failed to insert news") from exc

    async def _sync_tickers(self, news: LakeNews, tickers: list[str]) -> None:
        current = {row.ticker for row in news.tickers}
        desired = set(tickers)
        for row in list(news.tickers):
            if row.ticker not in desired:
                await self.db.delete(row)
        for ticker in desired - current:
            news.tickers.append(LakeNewsTicker(ticker=ticker))

    async def get_news_by_ticker(
        self, ticker: str, limit: int = 10, offset: int = 0
    ) -> list[LakeNews]:
        stmt = (
            select(LakeNews)
            .join(LakeNewsTicker)
            .filter(LakeNewsTicker.ticker == ticker.upper())
            .options(joinedload(LakeNews.tickers))
            .order_by(LakeNews.published_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_news_by_tickers(
        self, tickers: list[str], per_ticker_limit: int = 10
    ) -> dict[str, list[LakeNews]]:
        if not tickers:
            return {}
        tickers_u = [t.upper() for t in tickers]
        stmt = (
            select(LakeNews)
            .join(LakeNewsTicker)
            .filter(LakeNewsTicker.ticker.in_(tickers_u))
            .options(joinedload(LakeNews.tickers))
            .order_by(LakeNews.published_at.desc().nullslast())
            .limit(per_ticker_limit * len(tickers_u) * 3)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().unique().all()

        buckets: dict[str, list[LakeNews]] = {t: [] for t in tickers_u}
        for news in rows:
            for nt in news.tickers:
                if nt.ticker in buckets and len(buckets[nt.ticker]) < per_ticker_limit:
                    buckets[nt.ticker].append(news)
        return buckets

    async def upsert_ri_document(
        self,
        payload: LakeRIDocumentInternalSchema,
        company_id: uuid.UUID | None = None,
        source_slug: str = "cvm",
    ) -> LakeRIDocument:
        stmt = select(LakeRIDocument).filter(LakeRIDocument.doc_id == payload.doc_id)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        source_id = await _resolve_source_id(source_slug)
        if existing:
            existing.title = payload.title
            existing.text_excerpt = payload.text_excerpt
            existing.pdf_url = payload.pdf_url
            existing.reference_date = payload.reference_date
            if payload.delivered_at is not None:
                existing.delivered_at = payload.delivered_at
            existing.category = payload.category
            existing.ticker = payload.ticker.upper()
            if source_id is not None and existing.source_id is None:
                existing.source_id = source_id
            if company_id is not None:
                existing.company_id = company_id
            try:
                await self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                await self.db.rollback()
                logger.error(f"Update RI doc failed for {payload.doc_id}: {exc}")
                raise DatabaseError("Failed to update RI document") from exc

        document = LakeRIDocument(
            doc_id=payload.doc_id,
            company_id=company_id,
            ticker=payload.ticker.upper(),
            category=payload.category,
            title=payload.title,
            pdf_url=payload.pdf_url,
            text_excerpt=payload.text_excerpt,
            reference_date=payload.reference_date,
            delivered_at=payload.delivered_at,
            source_id=source_id,
        )
        self.db.add(document)
        try:
            await self.db.commit()
            await self.db.refresh(document)
            return document
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"Insert RI doc failed for {payload.doc_id}: {exc}")
            raise DatabaseError("Failed to insert RI document") from exc

    async def get_latest_ri_delivered_date(self) -> date | None:
        """Delivery date (Data_Entrega) of the most recent persisted RI doc.

        Used as the incremental cursor — the next crawl only processes rows
        with a delivery date strictly greater than this. Returns None on a
        cold start so the caller falls back to a full historical fetch.
        """
        stmt = select(func.max(LakeRIDocument.delivered_at))
        result = await self.db.execute(stmt)
        return result.scalar()

    async def get_ri_documents_by_ticker(self, ticker: str, limit: int = 3) -> list[LakeRIDocument]:
        stmt = (
            select(LakeRIDocument)
            .filter(LakeRIDocument.ticker == ticker.upper())
            .order_by(LakeRIDocument.reference_date.desc().nullslast())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_insight_cache(self, ticker: str) -> LakeInsightCache | None:
        stmt = select(LakeInsightCache).filter(LakeInsightCache.ticker == ticker.upper())
        result = await self.db.execute(stmt)
        cached = result.scalars().first()

        if not cached:
            return None
        if cached.expires_at and cached.expires_at < datetime.now(UTC):
            return None
        return cached

    async def upsert_insight_cache(
        self, ticker: str, payload: LakeInsightSchema, ttl_hours: int = 6
    ) -> LakeInsightCache:
        ticker = ticker.upper()
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

        stmt = select(LakeInsightCache).filter(LakeInsightCache.ticker == ticker)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.insight = payload.insight
            existing.score = payload.score
            existing.dy_adjusted = payload.dy_adjusted
            existing.pl_adjusted = payload.pl_adjusted
            existing.expires_at = expires_at
            try:
                await self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                await self.db.rollback()
                logger.error(f"Update insight failed for {ticker}: {exc}")
                raise DatabaseError("Failed to update insight cache") from exc

        cache = LakeInsightCache(
            ticker=ticker,
            insight=payload.insight,
            score=payload.score,
            dy_adjusted=payload.dy_adjusted,
            pl_adjusted=payload.pl_adjusted,
            expires_at=expires_at,
        )
        self.db.add(cache)
        try:
            await self.db.commit()
            await self.db.refresh(cache)
            return cache
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"Insert insight failed for {ticker}: {exc}")
            raise DatabaseError("Failed to insert insight cache") from exc
