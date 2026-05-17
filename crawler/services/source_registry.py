"""Process-local cache over the ``data_sources`` table.

Spiders call into this registry on every persisted row to attach a
``source_id`` FK and to honor the ``enabled`` kill-switch. The registry is
hot-reload friendly: when a row in ``data_sources`` is toggled (e.g. an
operator running ``UPDATE data_sources SET enabled=false WHERE slug='X'``
in response to a takedown), the next call to :meth:`SourceRegistry.refresh`
picks it up. By default the registry refreshes lazily after ``CACHE_TTL``
seconds — short enough for DMCA latency to feel instant in operator time.

The registry never invents a source: looking up a slug that isn't in the
DB raises ``SourceNotFoundError``. New sources are added via Alembic seed,
not by spider code, so the data lineage stays auditable.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler.models.models import DataSource
from crawler.services.database import session_local


class SourceNotFoundError(KeyError):
    """Raised when a spider asks for a slug that hasn't been seeded."""


@dataclass(frozen=True)
class SourceRecord:
    id: str  # UUID stringified; SQLAlchemy gives us the uuid object but we
             # immediately stringify for downstream serialization safety.
    slug: str
    display_name: str
    homepage_url: str
    tos_url: str | None
    license_label: str | None
    risk_tier: str
    enabled: bool


# Host → slug heuristics for backfills and RSS attribution. Order doesn't
# matter; each entry is a (substring, slug) pair matched against the URL host.
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
    """Singleton-style cache. Use :func:`get_source_registry`."""

    CACHE_TTL = 30.0  # seconds — short enough for kill-switch to feel instant.

    def __init__(self) -> None:
        self._by_slug: dict[str, SourceRecord] = {}
        self._loaded_at: float = 0.0
        self._lock = threading.Lock()

    def refresh(self, db: Session | None = None) -> None:
        """Force-reload from the database.

        Network/DB errors are swallowed and the previous cache (if any) is
        kept. This keeps spider tests runnable without a Postgres instance
        and protects production from a transient DB blip turning every
        source into a phantom-disabled one.
        """
        owns_session = db is None
        db_session: Session | None = None
        try:
            db_session = db if db is not None else session_local()
            rows = db_session.execute(select(DataSource)).scalars().all()
        except Exception as exc:
            logger.warning(
                "SourceRegistry: DB unreachable during refresh; "
                f"keeping previous cache of {len(self._by_slug)} entries. ({exc})"
            )
            return
        finally:
            if owns_session and db_session is not None:
                try:
                    db_session.close()
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
        with self._lock:
            self._by_slug = new_index
            self._loaded_at = time.monotonic()
        logger.debug(f"SourceRegistry: refreshed ({len(new_index)} sources).")

    def _ensure_loaded(self) -> None:
        # Cheap fast-path: most calls find a warm cache.
        if self._by_slug and (time.monotonic() - self._loaded_at) < self.CACHE_TTL:
            return
        self.refresh()

    def get(self, slug: str) -> SourceRecord:
        """Lookup by slug; raises if the source hasn't been seeded."""
        self._ensure_loaded()
        record = self._by_slug.get(slug)
        if record is None:
            # Maybe a freshly inserted source — refresh once and retry.
            self.refresh()
            record = self._by_slug.get(slug)
        if record is None:
            raise SourceNotFoundError(
                f"No data_sources row with slug={slug!r}. "
                "Seed it via Alembic before referencing from a spider."
            )
        return record

    def is_enabled(self, slug: str) -> bool:
        """Returns True unless the source is *explicitly* disabled in the registry.

        Fails open: unknown slugs (not yet seeded) and refresh failures both
        return True. The intent is for the kill-switch to require an
        affirmative ``UPDATE data_sources SET enabled=false WHERE slug='X'``,
        not for a missing migration or DB outage to silently halt collection.
        """
        try:
            return self.get(slug).enabled
        except SourceNotFoundError:
            return True

    def slug_for_url(self, url: str | None) -> str | None:
        """Heuristic host → slug mapping. Returns None when no hint matches.

        Used by the backfill script and by spiders that consume mixed-source
        feeds (e.g. the news spider, whose RSS entries can point at any of
        the four publishers). Not authoritative: the spider is free to pass
        an explicit slug when it knows better.
        """
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

    def all_enabled(self) -> list[SourceRecord]:
        """Snapshot of currently-enabled sources, sorted by display name."""
        self._ensure_loaded()
        return sorted(
            (r for r in self._by_slug.values() if r.enabled),
            key=lambda r: r.display_name.lower(),
        )


_registry: SourceRegistry | None = None


def get_source_registry() -> SourceRegistry:
    """Process-wide accessor. Always prefer this over instantiating directly."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry
