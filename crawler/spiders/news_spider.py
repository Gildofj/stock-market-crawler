import asyncio
import hashlib
import re
from datetime import UTC, datetime
from time import struct_time

import feedparser
from loguru import logger

from core.models.schemas import LakeNewsSchema
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from core.services.source_registry import get_source_registry

TICKER_PATTERN = re.compile(r"\b([A-Z]{4}[0-9]{1,2})\b")


class NewsSpider:
    """Collects financial news from Brazilian RSS feeds and tags them with tickers."""

    FEEDS: dict[str, str] = {
        "infomoney": "https://www.infomoney.com.br/feed/",
        "valor": "https://valor.globo.com/rss/",
        "investing": "https://br.investing.com/rss/news.rss",
        "money_times": "https://www.moneytimes.com.br/feed/",
    }

    def __init__(
        self,
        company_repo: CompanyRepository,
        lake_service: LakeService,
        known_tickers: set[str] | None = None,
    ):
        self.company_repo = company_repo
        self.lake_service = lake_service
        self._known_tickers = known_tickers

    async def _resolve_known_tickers(self) -> set[str]:
        if self._known_tickers is not None:
            return self._known_tickers
        symbols = await self.company_repo.get_all_symbols()
        self._known_tickers = symbols
        return symbols

    @staticmethod
    def _to_datetime(value: struct_time | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime(*value[:6], tzinfo=UTC)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _hash_url(url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def extract_tickers(self, text: str, known_tickers: set[str]) -> list[str]:
        if not text:
            return []
        candidates = {match.upper() for match in TICKER_PATTERN.findall(text)}
        candidates = {t for t in candidates if t.isalnum() and 4 <= len(t) <= 6}
        return sorted(candidates & known_tickers)

    async def crawl_all(self) -> int:
        known = await self._resolve_known_tickers()
        if not known:
            logger.warning("NewsSpider: no known tickers — skipping all feeds.")
            return 0

        registry = get_source_registry()
        persisted = 0
        for source, url in self.FEEDS.items():
            # Operator kill-switch: an UPDATE on data_sources.enabled stops the
            # spider from re-collecting from this feed within ~30s (cache TTL).
            if not await registry.is_enabled(source):
                logger.info(f"NewsSpider: skipping disabled source: {source}")
                continue
            try:
                # feedparser is sync, but we only do few network calls here
                feed = await asyncio.to_thread(feedparser.parse, url)
            except Exception as e:
                logger.error(f"NewsSpider: failed to parse feed {source}: {e}")
                continue

            if getattr(feed, "bozo", False) and feed.bozo:
                logger.warning(f"NewsSpider: feed {source} returned bozo flag.")

            for entry in getattr(feed, "entries", []) or []:
                link = getattr(entry, "link", None)
                title = getattr(entry, "title", None)
                if not link or not title:
                    continue

                text_blob = f"{title} {getattr(entry, 'summary', '')}"
                tickers = self.extract_tickers(text_blob, known)
                if not tickers:
                    continue

                payload = LakeNewsSchema(
                    source=source,
                    title=title[:500],
                    summary=getattr(entry, "summary", None),
                    url=link,
                    url_hash=self._hash_url(link),
                    sentiment=None,
                    published_at=self._to_datetime(
                        getattr(entry, "published_parsed", None)
                    )
                    or self._to_datetime(getattr(entry, "updated_parsed", None)),
                    tickers=tickers,
                )
                try:
                    await self.lake_service.upsert_news(payload)
                    persisted += 1
                except Exception as e:
                    logger.error(f"NewsSpider: upsert failed for {link}: {e}")

        logger.info(f"NewsSpider: persisted {persisted} news items.")
        return persisted
