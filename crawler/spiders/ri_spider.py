import asyncio
import io
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pdfplumber
from loguru import logger

from core.models.schemas import LakeRIDocumentInternalSchema
from core.repositories import CompanyRepository
from core.services.cnpj_map import resolve_ticker, watched_cnpjs
from core.services.lake_service import LakeService
from core.services.source_registry import get_source_registry
from crawler.services.request_manager import RequestManager


class RISpider:
    IPE_URL_TEMPLATE = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{year}.zip"
    )

    TARGET_CATEGORIES = {"ITR", "DFP", "FORMULARIO_DE_REFERENCIA", "FATO_RELEVANTE"}
    MAX_TEXT_CHARS = 10_000

    # CVM Dados Abertos publishes IPE going back to 2010. Cold-start runs walk
    # from here forward; subsequent runs resume from the latest persisted year.
    EARLIEST_IPE_YEAR = 2010

    def __init__(
        self,
        company_repo: CompanyRepository,
        lake_service: LakeService,
        request_manager: RequestManager | None = None,
    ):
        self.company_repo = company_repo
        self.lake_service = lake_service
        self.request_manager = request_manager or RequestManager()

    async def _fetch_index_csv(self, year: int) -> pd.DataFrame | None:
        url = self.IPE_URL_TEMPLATE.format(year=year)
        logger.info(f"RISpider: fetching IPE index for {year} ({url})")
        try:
            response = await self.request_manager.get_async(url, timeout=60, binary=True)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"RISpider: failed to fetch IPE index for {year}: {e}")
            return None

        def _parse_zip() -> pd.DataFrame:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                expected = f"ipe_cia_aberta_{year}.csv"
                csv_name = (
                    expected
                    if expected in archive.namelist()
                    else next((n for n in archive.namelist() if n.endswith(".csv")), None)
                )
                if csv_name is None:
                    raise ValueError(f"no CSV inside IPE archive for {year}")
                with archive.open(csv_name) as fh:
                    return pd.read_csv(fh, sep=";", encoding="latin-1")

        try:
            return await asyncio.to_thread(_parse_zip)
        except Exception as e:
            logger.error(f"RISpider: could not parse IPE archive for {year}: {e}")
            return None

    async def _fetch_pdf_bytes(self, pdf_url: str) -> bytes | None:
        try:
            response = await self.request_manager.get_async(pdf_url, timeout=90, binary=True)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"RISpider: failed to download PDF {pdf_url}: {e}")
            return None
        return response.content

    async def _extract_pdf_text(self, pdf_bytes: bytes, pdf_url: str | None = None) -> str | None:
        def _extract():
            try:
                buffer = io.BytesIO(pdf_bytes)
                with pdfplumber.open(buffer) as pdf:
                    chunks: list[str] = []
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        chunks.append(text)
                        if sum(len(c) for c in chunks) >= self.MAX_TEXT_CHARS:
                            break
                full = "\n".join(chunks).strip()
                return full[: self.MAX_TEXT_CHARS] if full else None
            except Exception as exc:
                logger.warning(f"RISpider: pdfplumber failed for {pdf_url or '<unknown>'}: {exc}")
                return None

        return await asyncio.to_thread(_extract)

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        if value is None:
            return None
        if not isinstance(value, str | int | float) and bool(pd.isna(value)):
            return None
        try:
            return pd.to_datetime(value).date()
        except (TypeError, ValueError):
            return None

    def _doc_id(self, row: pd.Series) -> str | None:
        candidates = ["Protocolo_Entrega", "ID_Documento", "Numero_Sequencial_Documento"]
        for column in candidates:
            if column in row.index and bool(pd.notna(row[column])):
                return str(row[column])
        return None

    async def _resolve_year_range(
        self,
        today: date,
        days_back: int | None,
        year: int | None,
    ) -> tuple[list[int], date, str]:
        if year is not None:
            return [year], date(year, 1, 1), "year"

        if days_back is not None:
            cutoff = today - timedelta(days=days_back)
            return list(range(cutoff.year, today.year + 1)), cutoff, "days_back"

        # Incremental: the current-year CSV is mutable (CVM appends new filings
        # throughout the year), so the cursor must be per-day, not per-year.
        latest_delivered = await self.lake_service.get_latest_ri_delivered_date()
        if latest_delivered is None:
            start_year = self.EARLIEST_IPE_YEAR
            cutoff = date(start_year, 1, 1)
            logger.info(
                f"RISpider: cold start — lake_ri_document has no delivered_at; "
                f"fetching from EARLIEST_IPE_YEAR={start_year}."
            )
        else:
            start_year = latest_delivered.year
            cutoff = latest_delivered + timedelta(days=1)
            logger.info(
                f"RISpider: incremental — latest delivered_at={latest_delivered}; "
                f"fetching rows with Data_Entrega >= {cutoff}."
            )
        return list(range(start_year, today.year + 1)), cutoff, "incremental"

    async def crawl_recent(
        self,
        days_back: int | None = None,
        year: int | None = None,
    ) -> int:
        import uuid

        if not await get_source_registry().is_enabled("cvm"):
            logger.info("RISpider: 'cvm' source disabled — skipping crawl.")
            return 0

        try:
            cvm_source = await get_source_registry().get("cvm")
            cvm_source_id = uuid.UUID(cvm_source.id)
        except Exception as e:
            logger.warning(f"RISpider: could not fetch 'cvm' source_id, lineage will be null: {e}")
            cvm_source_id = None

        today = datetime.utcnow().date()
        years_to_fetch, cutoff, mode = await self._resolve_year_range(today, days_back, year)

        logger.info(
            f"RISpider: crawl_recent(mode={mode}, days_back={days_back}, year={year}) "
            f"cutoff={cutoff} years_to_fetch={years_to_fetch}"
        )

        dfs: list[pd.DataFrame] = []
        for y in years_to_fetch:
            df_year = await self._fetch_index_csv(y)
            if df_year is None:
                logger.warning(f"RISpider: skipping {y} — IPE CSV unavailable.")
                continue
            if df_year.empty:
                logger.info(f"RISpider: IPE CSV for {y} is empty.")
                continue
            logger.info(f"RISpider: loaded {len(df_year)} rows from IPE CSV {y}.")
            dfs.append(df_year)

        if not dfs:
            logger.error(f"RISpider: no IPE CSV available for any of {years_to_fetch}; aborting.")
            return 0

        df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        logger.info(f"RISpider: concatenated {len(df)} raw rows across {len(dfs)} CSV(s).")

        cnpjs = watched_cnpjs()
        if "CNPJ_Companhia" not in df.columns:
            logger.error(
                f"RISpider: unexpected CSV schema (no CNPJ_Companhia). columns={list(df.columns)}"
            )
            return 0

        df["__cnpj"] = df["CNPJ_Companhia"].astype(str).str.replace(r"\D", "", regex=True)
        filtered: pd.DataFrame = df[df["__cnpj"].isin(list(cnpjs))]  # type: ignore[assignment] - Motivo: Injeção mock
        logger.info(
            f"RISpider: {len(filtered)} rows matched the {len(cnpjs)} watched CNPJs "
            f"(out of {len(df)} total)."
        )

        date_col = "Data_Entrega" if "Data_Entrega" in filtered.columns else None
        if date_col:
            filtered = filtered.assign(__date=pd.to_datetime(filtered[date_col], errors="coerce"))
            before_date = len(filtered)
            filtered = filtered[filtered["__date"].dt.date >= cutoff]  # type: ignore[assignment] - Motivo: Injeção mock
            logger.info(
                f"RISpider: {len(filtered)} rows pass date filter (>= {cutoff}); "
                f"dropped {before_date - len(filtered)}."
            )

        if "Categoria" in filtered.columns:
            before_cat = len(filtered)
            filtered = filtered[  # type: ignore[assignment] - Motivo: Injeção mock
                filtered["Categoria"].isin(list(self.TARGET_CATEGORIES))
            ]
            logger.info(
                f"RISpider: {len(filtered)} rows pass category filter "
                f"({self.TARGET_CATEGORIES}); dropped {before_cat - len(filtered)}."
            )

        if filtered.empty:
            logger.warning("RISpider: 0 rows survived filters; nothing to persist.")
            return 0

        skipped_no_doc_id = 0
        skipped_no_ticker = 0
        persisted = 0
        for _, row in filtered.iterrows():
            doc_id = self._doc_id(row)
            if not doc_id:
                skipped_no_doc_id += 1
                continue
            ticker = resolve_ticker(str(row["__cnpj"]))
            if not ticker:
                skipped_no_ticker += 1
                continue

            pdf_url_raw = row.get("Link_Download") or row.get("Link_Documento")
            pdf_url: str | None = (
                str(pdf_url_raw) if pdf_url_raw and pd.notna(pdf_url_raw) else None
            )

            text: str | None = None
            if pdf_url:
                pdf_bytes = await self._fetch_pdf_bytes(pdf_url)
                if pdf_bytes:
                    text = await self._extract_pdf_text(pdf_bytes, pdf_url)

            ref_value = row.get("Data_Referencia") or (row.get(date_col) if date_col else None)
            delivered_value = row.get(date_col) if date_col else None

            payload = LakeRIDocumentInternalSchema(
                doc_id=doc_id,
                ticker=ticker,
                category=str(row.get("Categoria") or "UNKNOWN"),
                title=str(row.get("Assunto") or row.get("Tipo") or doc_id)[:500],
                pdf_url=pdf_url,
                text_excerpt=text,
                reference_date=self._coerce_date(ref_value),
                delivered_at=self._coerce_date(delivered_value),
                source_id=cvm_source_id,
            )

            company = await self.company_repo.get_by_symbol(ticker)
            company_id = company.id if company else None

            try:
                await self.lake_service.upsert_ri_document(payload, company_id=company_id)
                persisted += 1
            except Exception as e:
                logger.error(f"RISpider: failed to persist {doc_id}: {e}")

        logger.info(
            f"RISpider: persisted {persisted} RI documents "
            f"(skipped_no_doc_id={skipped_no_doc_id}, "
            f"skipped_no_ticker={skipped_no_ticker})."
        )
        return persisted
