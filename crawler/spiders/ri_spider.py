import io
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pdfplumber
from loguru import logger

from ..models.schemas import LakeRIDocumentSchema
from ..services.cnpj_map import resolve_ticker, watched_cnpjs
from ..services.data_service import DataService
from ..services.lake_service import LakeService
from ..services.request_manager import RequestManager
from ..services.storage_service import R2Storage, get_storage


class RISpider:
    """Collects Brazilian RI documents (ITR/DFP/IPE) from CVM open data."""

    IPE_URL_TEMPLATE = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/"
        "ipe_cia_aberta_{year}.csv"
    )

    TARGET_CATEGORIES = {"ITR", "DFP", "FORMULARIO_DE_REFERENCIA", "FATO_RELEVANTE"}
    MAX_TEXT_CHARS = 10_000

    def __init__(
        self,
        data_service: DataService,
        lake_service: LakeService,
        request_manager: RequestManager | None = None,
        storage: R2Storage | None = None,
    ):
        self.data_service = data_service
        self.lake_service = lake_service
        self.request_manager = request_manager or RequestManager()
        self.storage = storage or get_storage()

    def _fetch_index_csv(self, year: int) -> pd.DataFrame | None:
        url = self.IPE_URL_TEMPLATE.format(year=year)
        try:
            response = self.request_manager.get(url, timeout=60)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"RISpider: failed to fetch IPE index for {year}: {e}")
            return None
        try:
            return pd.read_csv(
                io.BytesIO(response.content), sep=";", encoding="latin-1"
            )
        except Exception as e:
            logger.error(f"RISpider: could not parse IPE CSV for {year}: {e}")
            return None

    def _fetch_pdf_bytes(self, pdf_url: str) -> bytes | None:
        try:
            response = self.request_manager.get(pdf_url, timeout=90)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"RISpider: failed to download PDF {pdf_url}: {e}")
            return None
        return response.content

    def _extract_pdf_text(self, pdf_bytes: bytes, pdf_url: str | None = None) -> str | None:
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
        except Exception as e:
            logger.warning(f"RISpider: pdfplumber failed for {pdf_url or '<unknown>'}: {e}")
            return None

    @staticmethod
    def _r2_key_for(ticker: str, doc_id: str) -> str:
        safe_doc_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in doc_id)
        return f"{ticker.upper()}/{safe_doc_id}.pdf"

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

    def crawl_recent(self, days_back: int = 30, year: int | None = None) -> int:
        cutoff = datetime.utcnow().date() - timedelta(days=days_back)
        target_year = year or datetime.utcnow().year
        df = self._fetch_index_csv(target_year)
        if df is None or df.empty:
            return 0

        cnpjs = watched_cnpjs()
        if "CNPJ_Companhia" not in df.columns:
            logger.warning("RISpider: unexpected CSV schema, skipping.")
            return 0

        df["__cnpj"] = (
            df["CNPJ_Companhia"].astype(str).str.replace(r"\D", "", regex=True)
        )
        filtered: pd.DataFrame = df[df["__cnpj"].isin(list(cnpjs))]  # type: ignore[assignment]

        date_col = "Data_Entrega" if "Data_Entrega" in filtered.columns else None
        if date_col:
            filtered = filtered.assign(
                __date=pd.to_datetime(filtered[date_col], errors="coerce")
            )
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

            text: str | None = None
            r2_key: str | None = None
            r2_public_url: str | None = None
            if pdf_url:
                pdf_bytes = self._fetch_pdf_bytes(pdf_url)
                if pdf_bytes:
                    text = self._extract_pdf_text(pdf_bytes, pdf_url)
                    upload = self.storage.upload_ri_pdf(
                        self._r2_key_for(ticker, doc_id), pdf_bytes
                    )
                    if upload:
                        r2_key, r2_public_url = upload

            ref_value = row.get("Data_Referencia") or (row.get(date_col) if date_col else None)

            payload = LakeRIDocumentSchema(
                doc_id=doc_id,
                ticker=ticker,
                category=str(row.get("Categoria") or "UNKNOWN"),
                title=str(row.get("Assunto") or row.get("Tipo") or doc_id)[:500],
                pdf_url=pdf_url,
                text_excerpt=text,
                reference_date=self._coerce_date(ref_value),
                r2_public_url=r2_public_url,
            )

            company = self.data_service.get_company_by_symbol(ticker)
            company_id = company.id if company else None

            try:
                self.lake_service.upsert_ri_document(
                    payload, company_id=company_id, r2_key=r2_key
                )
                persisted += 1
            except Exception as e:
                logger.error(f"RISpider: failed to persist {doc_id}: {e}")

        logger.info(f"RISpider: persisted {persisted} RI documents.")
        return persisted
