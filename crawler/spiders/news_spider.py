import asyncio
import hashlib
import re
from datetime import UTC, datetime
from time import struct_time

import feedparser
from bs4 import BeautifulSoup
from loguru import logger

from core.models.schemas import LakeNewsSchema
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from core.services.source_registry import get_source_registry

TICKER_PATTERN = re.compile(r"\b([A-Z]{4}[0-9]{1,2})\b")

_B3_ISSUER_PREFIX_LEN = 4


def _issuer_prefix(ticker: str) -> str:
    return ticker[:_B3_ISSUER_PREFIX_LEN]


def _build_issuer_index(symbols: set[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for symbol in symbols:
        if len(symbol) < _B3_ISSUER_PREFIX_LEN:
            continue
        index.setdefault(_issuer_prefix(symbol), set()).add(symbol)
    return index


class NewsSpider:
    """Collects financial news from Brazilian RSS feeds and tags every sibling
    ticker of any issuer mentioned (a story citing PETR4 also gets PETR3)."""

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
        self._issuer_index: dict[str, set[str]] | None = (
            _build_issuer_index(known_tickers) if known_tickers is not None else None
        )

    async def _resolve_issuer_index(self) -> dict[str, set[str]]:
        if self._issuer_index is not None:
            return self._issuer_index
        symbols = await self.company_repo.get_all_symbols()
        self._issuer_index = _build_issuer_index(symbols)
        return self._issuer_index

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

    @staticmethod
    def _clean_html(text: str | None) -> str | None:
        if not text:
            return text
        return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)

    @staticmethod
    def extract_tickers(text: str, issuer_index: dict[str, set[str]]) -> list[str]:
        if not text:
            return []
        candidates = {match.upper() for match in TICKER_PATTERN.findall(text)}
        matched: set[str] = set()
        for candidate in candidates:
            siblings = issuer_index.get(_issuer_prefix(candidate))
            if siblings and candidate in siblings:
                matched.update(siblings)
        return sorted(matched)

    async def crawl_all(self) -> int:
        issuer_index = await self._resolve_issuer_index()
        if not issuer_index:
            logger.warning("NewsSpider: no known tickers — skipping all feeds.")
            return 0

        registry = get_source_registry()
        persisted = 0
        for source, url in self.FEEDS.items():
            if not await registry.is_enabled(source):
                logger.info(f"NewsSpider: skipping disabled source: {source}")
                continue
            try:
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
                tickers = self.extract_tickers(text_blob, issuer_index)
                if not tickers:
                    continue

                payload = LakeNewsSchema(
                    source=source,
                    title=self._clean_html(title)[:500] if title else "No Title",
                    summary=self._clean_html(getattr(entry, "summary", None)),
                    url=link,
                    url_hash=self._hash_url(link),
                    sentiment=None,
                    published_at=self._to_datetime(getattr(entry, "published_parsed", None))
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
