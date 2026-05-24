"""Refresh the B3 ticker universe in the ``companies`` table.

Runs as a Cloud Run Job (weekly cadence). Sequence:

1. Fetch ``/api/available`` from Brapi → list of all tradeable B3 tickers.
2. For each ticker not yet cached or whose ``updated_at`` is older than
   ``STALE_AFTER_DAYS``, fetch ``/api/quote/{ticker}?modules=summaryProfile``
   to get CNPJ + sector + asset type.
3. Cross-reference CNPJ with the CVM CAD dataset to resolve cd_cvm.
4. Upsert each row into ``companies``.

Operates under Brapi's free-tier monthly budget — skips refresh of rows that
were updated within ``STALE_AFTER_DAYS`` so a re-run mid-week is mostly a
no-op (just the /available call).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select

from core.database import session_local
from core.models.models import Company
from core.models.schemas import CompanySchema
from core.repositories.company_repository import CompanyRepository
from core.services.brapi_client import (
    BrapiClient,
    BrapiQuotaExceededError,
    BrapiQuote,
    BrapiUnauthorizedError,
    get_brapi_client,
)
from crawler.services.cvm_dataset_service import CVMDatasetService

STALE_AFTER_DAYS = 7


async def _existing_universe_index(repo: CompanyRepository) -> dict[str, Company]:
    result = await repo.db.execute(select(Company))
    rows = result.scalars().all()
    return {row.symbol.upper(): row for row in rows}


def _build_cnpj_to_cd_cvm(dataset: CVMDatasetService) -> dict[str, str]:
    cad = dataset.get_cad()
    if cad is None or "CNPJ_CIA" not in cad.columns or "CD_CVM" not in cad.columns:
        logger.warning("refresh_universe: CAD dataset unavailable; cd_cvm enrichment skipped.")
        return {}
    cnpj_digits = cad["CNPJ_CIA"].fillna("").astype(str).str.replace(r"\D", "", regex=True)
    cd_cvm = cad["CD_CVM"].astype(str)
    return {c: code for c, code in zip(cnpj_digits, cd_cvm, strict=False) if c}


def _is_stale(company: Company | None) -> bool:
    if company is None:
        return True
    if company.cnpj is None or company.asset_type is None:
        return True
    if company.updated_at is None:
        return True
    age = datetime.now(UTC) - company.updated_at.astimezone(UTC)
    return age > timedelta(days=STALE_AFTER_DAYS)


def _underlying_ticker_for(quote: BrapiQuote) -> str | None:
    if quote.asset_type != "BDR":
        return None
    underlying = quote.raw.get("underlyingSymbol") or quote.raw.get("underlying")
    if underlying:
        return str(underlying).upper()
    return None


async def _refresh_one(
    symbol: str,
    repo: CompanyRepository,
    client: BrapiClient,
    cnpj_to_cd_cvm: dict[str, str],
) -> tuple[str, str]:
    """Refresh a single ticker. Returns (symbol, status_label) for log aggregation."""
    quote = client.fetch_quote(symbol)
    if quote is None:
        return symbol, "no_metadata"

    payload = CompanySchema(
        symbol=symbol,
        name=quote.long_name or symbol,
        sector=quote.sector,
        sub_sector=quote.industry,
        cnpj=quote.cnpj,
        cd_cvm=cnpj_to_cd_cvm.get(quote.cnpj) if quote.cnpj else None,
        asset_type=quote.asset_type,
        underlying_ticker=_underlying_ticker_for(quote),
    )
    await repo.get_or_create(payload)
    return symbol, "refreshed"


async def _run_refresh() -> dict[str, int]:
    client = get_brapi_client()
    if not client.enabled:
        logger.error("refresh_universe: BRAPI_TOKEN not configured; aborting.")
        return {"aborted": 1}

    db = session_local()
    try:
        repo = CompanyRepository(db)

        try:
            tickers = await asyncio.to_thread(client.list_available_tickers)
        except BrapiUnauthorizedError as exc:
            logger.error(f"refresh_universe: {exc}")
            return {"aborted": 1}
        except BrapiQuotaExceededError as exc:
            logger.error(f"refresh_universe: {exc}")
            return {"aborted": 1}

        logger.info(f"refresh_universe: Brapi returned {len(tickers)} tickers.")

        existing = await _existing_universe_index(repo)
        targets = [t for t in tickers if _is_stale(existing.get(t))]
        logger.info(
            f"refresh_universe: {len(targets)} tickers stale or new "
            f"(out of {len(tickers)}); skipping {len(tickers) - len(targets)} fresh entries."
        )

        if not targets:
            return {"checked": len(tickers), "refreshed": 0, "skipped": len(tickers)}

        cnpj_to_cd_cvm = await asyncio.to_thread(_build_cnpj_to_cd_cvm, CVMDatasetService())

        counters = {"refreshed": 0, "no_metadata": 0, "errors": 0, "quota_exceeded": 0}
        for symbol in targets:
            try:
                _, status = await _refresh_one(symbol, repo, client, cnpj_to_cd_cvm)
                counters[status] = counters.get(status, 0) + 1
            except BrapiQuotaExceededError:
                logger.warning(
                    f"refresh_universe: Brapi quota exhausted after {counters['refreshed']} "
                    "refreshes; aborting remaining tickers."
                )
                counters["quota_exceeded"] = 1
                break
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
    task_logger.info("Starting Brapi-driven ticker universe refresh...")
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
