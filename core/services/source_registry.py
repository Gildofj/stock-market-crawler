from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import session_local
from core.models.models import DataSource


class SourceNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class SourceRecord:
    id: str
    slug: str
    display_name: str
    homepage_url: str
    tos_url: str | None
    license_label: str | None
    risk_tier: str
    enabled: bool


_HOST_HINTS: tuple[tuple[str, str], ...] = (
    ("cvm.gov.br", "cvm"),
    ("bcb.gov.br", "bcb"),
    ("b3.com.br", "b3"),
    ("infomoney.com.br", "infomoney"),
    ("valor.globo.com", "valor"),
    ("valoreconomico.com.br", "valor"),
    ("investing.com", "investing"),
    ("moneytimes.com.br", "money_times"),
    ("yahoo.com", "yfinance"),
    ("yahoofinance", "yfinance"),
)


class SourceRegistry:
    CACHE_TTL = 30.0

    def __init__(self) -> None:
        self._by_slug: dict[str, SourceRecord] = {}
        self._loaded_at: float = 0.0
        self._lock = asyncio.Lock()

    async def refresh(self, db: AsyncSession | None = None) -> None:
        owns_session = db is None
        db_session: AsyncSession | None = None
        try:
            db_session = db if db is not None else session_local()
            result = await db_session.execute(select(DataSource))
            rows = result.scalars().all()
        except Exception as exc:
            logger.warning(
                "SourceRegistry: DB unreachable during refresh; "
                f"keeping previous cache of {len(self._by_slug)} entries. ({exc})"
            )
            return
        finally:
            if owns_session and db_session is not None:
                try:
                    await db_session.close()
                except Exception:
                    pass

        new_index: dict[str, SourceRecord] = {}
        for row in rows:
            new_index[row.slug] = SourceRecord(
                id=str(row.id),
                slug=row.slug,
                display_name=row.display_name,
                homepage_url=row.homepage_url,
                tos_url=row.tos_url,
                license_label=row.license_label,
                risk_tier=row.risk_tier,
                enabled=row.enabled,
            )
        async with self._lock:
            self._by_slug = new_index
            self._loaded_at = time.monotonic()
        logger.debug(f"SourceRegistry: refreshed ({len(new_index)} sources).")

    async def _ensure_loaded(self) -> None:
        if self._by_slug and (time.monotonic() - self._loaded_at) < self.CACHE_TTL:
            return
        await self.refresh()

    async def get(self, slug: str) -> SourceRecord:
        await self._ensure_loaded()
        record = self._by_slug.get(slug)
        if record is None:
            await self.refresh()
            record = self._by_slug.get(slug)
        if record is None:
            raise SourceNotFoundError(
                f"No data_sources row with slug={slug!r}. "
                "Seed it via Alembic before referencing from a spider."
            )
        return record

    async def is_enabled(self, slug: str) -> bool:
        try:
            record = await self.get(slug)
            return record.enabled
        except SourceNotFoundError:
            return True

    def slug_for_url(self, url: str | None) -> str | None:
        if not url:
            return None
        try:
            host = urlparse(url).netloc.lower()
        except (ValueError, AttributeError):
            return None
        if not host:
            return None
        for hint, slug in _HOST_HINTS:
            if hint in host:
                return slug
        return None

    async def all_enabled(self) -> list[SourceRecord]:
        await self._ensure_loaded()
        return sorted(
            (r for r in self._by_slug.values() if r.enabled),
            key=lambda r: r.display_name.lower(),
        )


_registry: SourceRegistry | None = None


def get_source_registry() -> SourceRegistry:
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry
