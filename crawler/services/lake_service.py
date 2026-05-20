import uuid
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ..models.models import LakeInsightCache, LakeNews, LakeNewsTicker, LakeRIDocument
from ..models.schemas import (
    LakeInsightSchema,
    LakeNewsSchema,
    LakeRIDocumentInternalSchema,
)
from .exceptions import DatabaseError
from .source_registry import SourceNotFoundError, get_source_registry


def _resolve_source_id(slug: str | None) -> uuid.UUID | None:
    """Best-effort lookup of a slug → data_sources.id. Returns None on miss.

    Persistence stays nullable on purpose: a missing slug is a soft signal
    (e.g. enrichment from a legacy spider that hasn't been wired yet), not
    a reason to drop the row.
    """
    if not slug:
        return None
    try:
        return uuid.UUID(get_source_registry().get(slug).id)
    except SourceNotFoundError:
        logger.warning(f"LakeService: unknown source slug {slug!r}; persisting without FK.")
        return None


class LakeService:
    def __init__(self, db: Session):
        self.db = db

    def upsert_news(self, payload: LakeNewsSchema) -> LakeNews:
        existing = (
            self.db.query(LakeNews).filter(LakeNews.url_hash == payload.url_hash).first()
        )

        source_id = _resolve_source_id(payload.source)

        if existing:
            existing.title = payload.title
            existing.summary = payload.summary
            existing.sentiment = payload.sentiment
            existing.published_at = payload.published_at
            if source_id is not None and existing.source_id is None:
                existing.source_id = source_id
            self._sync_tickers(existing, payload.tickers)
            try:
                self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                self.db.rollback()
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
            self.db.commit()
            self.db.refresh(news)
            return news
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Insert news failed for {payload.url}: {exc}")
            raise DatabaseError("Failed to insert news") from exc

    def _sync_tickers(self, news: LakeNews, tickers: list[str]) -> None:
        current = {row.ticker for row in news.tickers}
        desired = set(tickers)
        for row in list(news.tickers):
            if row.ticker not in desired:
                self.db.delete(row)
        for ticker in desired - current:
            news.tickers.append(LakeNewsTicker(ticker=ticker))

    def get_news_by_ticker(
        self, ticker: str, limit: int = 10, offset: int = 0
    ) -> list[LakeNews]:
        return (
            self.db.query(LakeNews)
            .join(LakeNewsTicker)
            .filter(LakeNewsTicker.ticker == ticker.upper())
            .options(joinedload(LakeNews.tickers))
            .order_by(LakeNews.published_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_news_by_tickers(
        self, tickers: list[str], per_ticker_limit: int = 10
    ) -> dict[str, list[LakeNews]]:
        """Bulk news lookup for the portfolio snapshot endpoint.

        Single `.in_()` query + Python-side bucketing keeps the round-trip
        count at 1 and stays dialect-agnostic (no window functions, so it
        runs identically on PostgreSQL and SQLite). One news row that is
        tagged with multiple tickers in the request will appear in every
        matching bucket — that is the correct behavior for dashboards.

        The hard `limit` on the SQL side is a defensive overfetch cap that
        prevents pathological responses if a single ticker has thousands of
        recent news.
        """
        if not tickers:
            return {}
        tickers_u = [t.upper() for t in tickers]
        rows = (
            self.db.query(LakeNews)
            .join(LakeNewsTicker)
            .filter(LakeNewsTicker.ticker.in_(tickers_u))
            .options(joinedload(LakeNews.tickers))
            .order_by(LakeNews.published_at.desc().nullslast())
            .limit(per_ticker_limit * len(tickers_u) * 3)
            .all()
        )
        buckets: dict[str, list[LakeNews]] = {t: [] for t in tickers_u}
        for news in rows:
            for nt in news.tickers:
                if nt.ticker in buckets and len(buckets[nt.ticker]) < per_ticker_limit:
                    buckets[nt.ticker].append(news)
        return buckets

    def upsert_ri_document(
        self,
        payload: LakeRIDocumentInternalSchema,
        company_id: uuid.UUID | None = None,
        r2_key: str | None = None,
        source_slug: str = "cvm",
    ) -> LakeRIDocument:
        existing = (
            self.db.query(LakeRIDocument)
            .filter(LakeRIDocument.doc_id == payload.doc_id)
            .first()
        )
        source_id = _resolve_source_id(source_slug)

        if existing:
            existing.title = payload.title
            existing.text_excerpt = payload.text_excerpt
            existing.pdf_url = payload.pdf_url
            existing.reference_date = payload.reference_date
            existing.category = payload.category
            existing.ticker = payload.ticker.upper()
            if source_id is not None and existing.source_id is None:
                existing.source_id = source_id
            if r2_key is not None:
                existing.r2_key = r2_key
            if payload.r2_public_url is not None:
                existing.r2_public_url = payload.r2_public_url
            if company_id is not None:
                existing.company_id = company_id
            try:
                self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                self.db.rollback()
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
            r2_key=r2_key,
            r2_public_url=payload.r2_public_url,
            source_id=source_id,
        )
        self.db.add(document)
        try:
            self.db.commit()
            self.db.refresh(document)
            return document
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Insert RI doc failed for {payload.doc_id}: {exc}")
            raise DatabaseError("Failed to insert RI document") from exc

    def get_ri_documents_by_ticker(
        self, ticker: str, limit: int = 3
    ) -> list[LakeRIDocument]:
        return (
            self.db.query(LakeRIDocument)
            .filter(LakeRIDocument.ticker == ticker.upper())
            .order_by(LakeRIDocument.reference_date.desc().nullslast())
            .limit(limit)
            .all()
        )

    def get_insight_cache(self, ticker: str) -> LakeInsightCache | None:
        cached = (
            self.db.query(LakeInsightCache)
            .filter(LakeInsightCache.ticker == ticker.upper())
            .first()
        )
        if not cached:
            return None
        if cached.expires_at and cached.expires_at < datetime.now(UTC):
            return None
        return cached

    def upsert_insight_cache(
        self, ticker: str, payload: LakeInsightSchema, ttl_hours: int = 6
    ) -> LakeInsightCache:
        ticker = ticker.upper()
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

        existing = (
            self.db.query(LakeInsightCache)
            .filter(LakeInsightCache.ticker == ticker)
            .first()
        )
        if existing:
            existing.insight = payload.insight
            existing.score = payload.score
            existing.dy_adjusted = payload.dy_adjusted
            existing.pl_adjusted = payload.pl_adjusted
            existing.expires_at = expires_at
            try:
                self.db.commit()
                return existing
            except SQLAlchemyError as exc:
                self.db.rollback()
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
            self.db.commit()
            self.db.refresh(cache)
            return cache
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Insert insight failed for {ticker}: {exc}")
            raise DatabaseError("Failed to insert insight cache") from exc
