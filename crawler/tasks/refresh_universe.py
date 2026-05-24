"""Refresh the B3 ticker universe in the ``companies`` table.

Runs as a Cloud Run Job (weekly cadence). Sequence:

1. Fetch B3 Catalog Service → list of all tradeable B3 tickers.
2. Fetch CVM CAD dataset → CNPJ, CD_CVM, DENOM_SOCIAL, SETOR_ATIV.
3. Fetch B3 BDR Catalog Service → BDR underlying tickers and ratios.
4. Match B3 issuer names with CVM DENOM_SOCIAL using difflib.
5. Upsert each row into ``companies``.
"""

from __future__ import annotations

import asyncio
import difflib
from datetime import UTC, datetime, timedelta

import pandas as pd
from loguru import logger
from sqlalchemy import select

from core.database import session_local
from core.models.models import Company
from core.models.schemas import CompanySchema
from core.repositories.company_repository import CompanyRepository
from crawler.services.b3_bdr_catalog_service import B3BDRCatalogService
from crawler.services.b3_catalog_service import B3CatalogService
from crawler.services.cvm_dataset_service import CVMDatasetService

STALE_AFTER_DAYS = 7


async def _existing_universe_index(repo: CompanyRepository) -> dict[str, Company]:
    result = await repo.db.execute(select(Company))
    rows = result.scalars().all()
    return {row.symbol.upper(): row for row in rows}


def _is_stale(company: Company | None) -> bool:
    if company is None:
        return True
    if company.asset_type is None:
        return True
    if company.updated_at is None:
        return True
    age = datetime.now(UTC) - company.updated_at.astimezone(UTC)
    return age > timedelta(days=STALE_AFTER_DAYS)


def _match_cvm_company(b3_issuer_name: str, cad_df: pd.DataFrame | None) -> dict | None:
    if not b3_issuer_name or cad_df is None or cad_df.empty:
        return None

    b3_name_upper = str(b3_issuer_name).upper().strip()

    # Fast exact match
    exact = cad_df[cad_df["DENOM_SOCIAL"].str.upper().str.strip() == b3_name_upper]
    if not exact.empty:
        row = exact.iloc[0]
        return {
            "cnpj": str(row.get("CNPJ_CIA", "")).replace(r"\D", ""),
            "cd_cvm": str(row.get("CD_CVM", "")).strip(),
            "sector": str(row.get("SETOR_ATIV", "")).strip() or None,
        }

    # Difflib match
    best_ratio = 0.0
    best_row = None
    for _, row in cad_df.iterrows():
        denom = str(row.get("DENOM_SOCIAL", "")).upper().strip()
        if not denom:
            continue
        ratio = difflib.SequenceMatcher(None, b3_name_upper, denom).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_row = row

    if best_ratio > 0.9 and best_row is not None:
        return {
            "cnpj": str(best_row.get("CNPJ_CIA", "")).replace(r"\D", ""),
            "cd_cvm": str(best_row.get("CD_CVM", "")).strip(),
            "sector": str(best_row.get("SETOR_ATIV", "")).strip() or None,
        }

    return None


async def _refresh_one(
    symbol: str,
    repo: CompanyRepository,
    b3_catalog: B3CatalogService,
    bdr_catalog: dict[str, tuple[str, float]],
    cad_df: pd.DataFrame | None,
) -> tuple[str, str]:
    df_catalog = b3_catalog._get_catalog()
    if df_catalog is None or df_catalog.empty:
        return symbol, "no_metadata"

    row = df_catalog[df_catalog["ticker"] == symbol]
    if row.empty:
        return symbol, "no_metadata"

    item = row.iloc[0]
    issuer_name = item.get("issuer_name")

    asset_type = b3_catalog.classify(symbol)

    cvm_data = _match_cvm_company(issuer_name, cad_df) if issuer_name else None

    underlying_ticker = None
    bdr_ratio = None
    if asset_type == "BDR":
        if symbol in bdr_catalog:
            underlying_ticker, bdr_ratio = bdr_catalog[symbol]

    payload = CompanySchema(
        symbol=symbol,
        name=issuer_name or symbol,
        sector=cvm_data["sector"] if cvm_data else None,
        sub_sector=None,
        cnpj=cvm_data["cnpj"] if cvm_data else None,
        cd_cvm=cvm_data["cd_cvm"] if cvm_data else None,
        asset_type=asset_type,
        underlying_ticker=underlying_ticker,
        bdr_ratio=bdr_ratio,
    )
    await repo.get_or_create(payload)
    return symbol, "refreshed"


async def _run_refresh() -> dict[str, int]:
    db = session_local()
    try:
        repo = CompanyRepository(db)

        b3_catalog = B3CatalogService()
        tickers = await asyncio.to_thread(b3_catalog.list_tickers)
        if not tickers:
            logger.error("refresh_universe: failed to fetch tickers from B3.")
            return {"aborted": 1}

        logger.info(f"refresh_universe: B3 returned {len(tickers)} tickers.")

        existing = await _existing_universe_index(repo)
        targets = [t for t in tickers if _is_stale(existing.get(t))]
        logger.info(
            f"refresh_universe: {len(targets)} tickers stale or new "
            f"(out of {len(tickers)}); skipping {len(tickers) - len(targets)} fresh entries."
        )

        if not targets:
            return {"checked": len(tickers), "refreshed": 0, "skipped": len(tickers)}

        dataset_service = CVMDatasetService()
        cad_df = await asyncio.to_thread(dataset_service.get_cad)

        bdr_service = B3BDRCatalogService()
        bdr_catalog = await asyncio.to_thread(bdr_service.get_bdr_metadata)

        counters = {"refreshed": 0, "no_metadata": 0, "errors": 0}
        for symbol in targets:
            try:
                _, status = await _refresh_one(symbol, repo, b3_catalog, bdr_catalog, cad_df)
                counters[status] = counters.get(status, 0) + 1
            except Exception as exc:
                logger.warning(f"refresh_universe: failed for {symbol}: {exc}")
                counters["errors"] += 1

        counters["checked"] = len(tickers)
        counters["skipped"] = len(tickers) - len(targets)
        logger.info(f"refresh_universe: done {counters}")
        return counters
    finally:
        await db.close()


async def refresh_universe_task() -> dict[str, int]:
    task_logger = logger.bind(task="refresh_universe")
    task_logger.info("Starting B3-driven ticker universe refresh...")
    try:
        return await _run_refresh()
    except Exception as exc:
        task_logger.error(f"refresh_universe: task failed: {exc}")
        raise


def main() -> None:
    from core.logging import setup_logging
    from core.telemetry import setup_tracing, shutdown_tracing

    setup_logging()
    setup_tracing("refresh-universe")

    job_logger = logger.bind(task="refresh_universe", runtime="cloud_run_job")
    job_logger.info("Starting refresh_universe (Cloud Run Job)...")
    try:
        asyncio.run(refresh_universe_task())
        job_logger.info("refresh_universe completed.")
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
