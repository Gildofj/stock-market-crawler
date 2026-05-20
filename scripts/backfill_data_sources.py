"""One-shot backfill of source_id FKs on rows persisted before the registry existed.

Idempotent: every UPDATE filters on ``source_id IS NULL`` so re-running the
script after partial completion picks up where it left off without touching
rows that already have a value.

Strategy:

* ``lake_news`` — match on the legacy ``source`` column (already a slug-like
  string). If the slug exists in ``data_sources``, set ``source_id``.
* ``lake_ri_documents`` — every row came from CVM, so default to ``'cvm'``.
* ``stock_prices`` — historically populated by yfinance via the b3 enrichment
  chain; default to ``'yfinance'`` for safety. Operators with a different
  provenance can pass ``--prices-slug``.
* ``companies.metadata_source_id`` — left NULL unless ``--companies-slug`` is
  given; we don't know retroactively which spider populated each row.
* ``fundamentals.primary_source_id`` — same as companies: NULL by default,
  override available.

Run with:

    uv run python scripts/backfill_data_sources.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import session_local


async def _execute(db: AsyncSession, sql: str, *, dry_run: bool, label: str) -> int:
    if dry_run:
        # In dry-run we count what would change but don't write.
        count_sql = sql.replace("UPDATE", "SELECT count(*) FROM").split("SET")[0]
        try:
            res = await db.execute(text(count_sql))
            result = res.scalar() or 0
        except Exception as exc:
            logger.warning(f"{label}: could not estimate row count in dry-run ({exc})")
            return 0
        logger.info(f"{label}: would update ~{result} rows.")
        return int(result)
    
    result = await db.execute(text(sql))
    rowcount = result.rowcount or 0
    logger.info(f"{label}: updated {rowcount} rows.")
    return rowcount


async def backfill(
    dry_run: bool,
    ri_slug: str,
    prices_slug: str,
    companies_slug: str | None,
    fundamentals_slug: str | None,
) -> int:
    total = 0
    db = session_local()
    try:
        total += await _execute(
            db,
            """
            UPDATE lake_news AS ln
            SET source_id = ds.id
            FROM data_sources AS ds
            WHERE ln.source_id IS NULL
              AND ds.slug = ln.source
            """,
            dry_run=dry_run,
            label="lake_news.source_id (match by legacy 'source' string)",
        )
        total += await _execute(
            db,
            f"""
            UPDATE lake_ri_documents AS lr
            SET source_id = ds.id
            FROM data_sources AS ds
            WHERE lr.source_id IS NULL
              AND ds.slug = '{ri_slug}'
            """,
            dry_run=dry_run,
            label=f"lake_ri_documents.source_id := '{ri_slug}'",
        )
        total += await _execute(
            db,
            f"""
            UPDATE stock_prices AS sp
            SET source_id = ds.id
            FROM data_sources AS ds
            WHERE sp.source_id IS NULL
              AND ds.slug = '{prices_slug}'
            """,
            dry_run=dry_run,
            label=f"stock_prices.source_id := '{prices_slug}'",
        )
        if companies_slug:
            total += await _execute(
                db,
                f"""
                UPDATE companies AS c
                SET metadata_source_id = ds.id
                FROM data_sources AS ds
                WHERE c.metadata_source_id IS NULL
                  AND ds.slug = '{companies_slug}'
                """,
                dry_run=dry_run,
                label=f"companies.metadata_source_id := '{companies_slug}'",
            )
        if fundamentals_slug:
            total += await _execute(
                db,
                f"""
                UPDATE fundamentals AS f
                SET primary_source_id = ds.id
                FROM data_sources AS ds
                WHERE f.primary_source_id IS NULL
                  AND ds.slug = '{fundamentals_slug}'
                """,
                dry_run=dry_run,
                label=f"fundamentals.primary_source_id := '{fundamentals_slug}'",
            )

        if dry_run:
            await db.rollback()
            logger.info(f"DRY RUN: estimated {total} affected rows; nothing written.")
        else:
            await db.commit()
            logger.info(f"Done. Total rows updated: {total}.")
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
    return total


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill data_sources FKs on legacy rows.")
    p.add_argument("--dry-run", action="store_true", help="Report counts; write nothing.")
    p.add_argument("--ri-slug", default="cvm")
    p.add_argument("--prices-slug", default="yfinance")
    p.add_argument(
        "--companies-slug",
        default=None,
        help="Slug to attribute company metadata to (e.g. 'b3'). NULL if omitted.",
    )
    p.add_argument(
        "--fundamentals-slug",
        default="cvm",
        help=(
            "Slug to attribute legacy fundamentals rows to. Defaults to 'cvm' "
            "now that the pipeline computes indicators locally from CVM open data."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    affected = asyncio.run(
        backfill(
            dry_run=args.dry_run,
            ri_slug=args.ri_slug,
            prices_slug=args.prices_slug,
            companies_slug=args.companies_slug,
            fundamentals_slug=args.fundamentals_slug,
        )
    )
    return 0 if affected >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
