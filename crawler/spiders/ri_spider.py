import asyncio
import io
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
    """Collects Brazilian RI documents (ITR/DFP/IPE) from CVM open data.

    PDFs are *not* mirrored. Persisted records keep the upstream CVM URL
    (``pdf_url``) and a length-capped text excerpt extracted in-memory; both
    the public R2 mirror and the bucket key are intentionally unset. See
    DISCLAIMER.md for the rationale.
    """

    IPE_URL_TEMPLATE = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{year}.csv"
    )

    TARGET_CATEGORIES = {"ITR", "DFP", "FORMULARIO_DE_REFERENCIA", "FATO_RELEVANTE"}
    MAX_TEXT_CHARS = 10_000

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
        try:
            response = await self.request_manager.get_async(url, timeout=60)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"RISpider: failed to fetch IPE index for {year}: {e}")
            return None
        try:
            # pandas.read_csv is sync, but small network-bound overhead here
            return await asyncio.to_thread(
                lambda: pd.read_csv(io.BytesIO(response.content), sep=";", encoding="latin-1")
            )
        except Exception as e:
            logger.error(f"RISpider: could not parse IPE CSV for {year}: {e}")
            return None

    async def _fetch_pdf_bytes(self, pdf_url: str) -> bytes | None:
        try:
            response = await self.request_manager.get_async(pdf_url, timeout=90)
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

    async def crawl_recent(self, days_back: int = 30, year: int | None = None) -> int:
        import uuid

        # Operator kill-switch: disabling 'cvm' in data_sources halts new
        # collection without a deploy. Existing rows are unaffected.
        if not await get_source_registry().is_enabled("cvm"):
            logger.info("RISpider: 'cvm' source disabled — skipping crawl.")
            return 0

        try:
            cvm_source = await get_source_registry().get("cvm")
            cvm_source_id = uuid.UUID(cvm_source.id)
        except Exception as e:
            logger.warning(f"RISpider: could not fetch 'cvm' source_id, lineage will be null: {e}")
            cvm_source_id = None

        cutoff = datetime.utcnow().date() - timedelta(days=days_back)
        target_year = year or datetime.utcnow().year

        dfs = []
        df_current = await self._fetch_index_csv(target_year)
        if df_current is not None and not df_current.empty:
            dfs.append(df_current)

        if year is None and (cutoff.year < target_year or df_current is None):
            df_prev = await self._fetch_index_csv(target_year - 1)
            if df_prev is not None and not df_prev.empty:
                dfs.append(df_prev)

        if not dfs:
            return 0

        df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

        cnpjs = watched_cnpjs()
        if "CNPJ_Companhia" not in df.columns:
            logger.warning("RISpider: unexpected CSV schema, skipping.")
            return 0

        df["__cnpj"] = df["CNPJ_Companhia"].astype(str).str.replace(r"\D", "", regex=True)
        filtered: pd.DataFrame = df[df["__cnpj"].isin(list(cnpjs))]  # type: ignore[assignment]

        date_col = "Data_Entrega" if "Data_Entrega" in filtered.columns else None
        if date_col:
            filtered = filtered.assign(__date=pd.to_datetime(filtered[date_col], errors="coerce"))
            filtered = filtered[filtered["__date"].dt.date >= cutoff]  # type: ignore[assignment]

        if "Categoria" in filtered.columns:
            filtered = filtered[  # type: ignore[assignment]
                filtered["Categoria"].isin(list(self.TARGET_CATEGORIES))
            ]

        persisted = 0
        for _, row in filtered.iterrows():
            doc_id = self._doc_id(row)
            if not doc_id:
                continue
            ticker = resolve_ticker(str(row["__cnpj"]))
            if not ticker:
                continue

            pdf_url_raw = row.get("Link_Download") or row.get("Link_Documento")
            pdf_url: str | None = (
                str(pdf_url_raw) if pdf_url_raw and pd.notna(pdf_url_raw) else None
            )

            # PDFs are fetched only to extract the text excerpt; the bytes are
            # never mirrored. The upstream CVM URL is the only redistributable
            # reference we keep.
            text: str | None = None
            if pdf_url:
                pdf_bytes = await self._fetch_pdf_bytes(pdf_url)
                if pdf_bytes:
                    text = await self._extract_pdf_text(pdf_bytes, pdf_url)

            ref_value = row.get("Data_Referencia") or (row.get(date_col) if date_col else None)

            payload = LakeRIDocumentInternalSchema(
                doc_id=doc_id,
                ticker=ticker,
                category=str(row.get("Categoria") or "UNKNOWN"),
                title=str(row.get("Assunto") or row.get("Tipo") or doc_id)[:500],
                pdf_url=pdf_url,
                text_excerpt=text,
                reference_date=self._coerce_date(ref_value),
                r2_public_url=None,
                source_id=cvm_source_id,
            )

            company = await self.company_repo.get_by_symbol(ticker)
            company_id = company.id if company else None

            try:
                await self.lake_service.upsert_ri_document(
                    payload, company_id=company_id, r2_key=None
                )
                persisted += 1
            except Exception as e:
                logger.error(f"RISpider: failed to persist {doc_id}: {e}")

        logger.info(f"RISpider: persisted {persisted} RI documents.")
        return persisted
