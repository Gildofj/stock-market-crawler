"""Downloads and parses CVM open-data financial-statement ZIPs.

The CVM publishes every listed company's standardized statements under
``https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/...``. Each year's package is
distributed as a single ZIP containing one CSV per statement and per scope
(individual ``ind`` vs. consolidated ``con``). The files are large
(~50–150 MB), so we cache them on disk in ``CVM_CACHE_DIR`` (default:
``$TMPDIR/cvm_cache``). Re-downloads only happen when the cached file is
older than ``CVM_CACHE_TTL_HOURS`` (default 24h) or missing.

This module is intentionally narrow: it knows how to *fetch* and *parse*
into pandas DataFrames. Account-code interpretation lives in the
CVMSpider, which is the only consumer.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from loguru import logger

from .request_manager import RequestManager

Scope = Literal["con", "ind"]
Statement = Literal["BPA", "BPP", "DRE", "DFC_MD", "DFC_MI", "DMPL", "DVA"]

_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"


def _default_cache_dir() -> Path:
    override = os.getenv("CVM_CACHE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "cvm_cache"


@dataclass(frozen=True)
class CVMYearData:
    """Parsed statements for one (year, scope) tuple.

    Each statement is a DataFrame indexed by ``(CD_CVM, DT_REFER)`` with one
    row per account; consumers filter by company code and reference date.
    """

    year: int
    doc_type: Literal["DFP", "ITR"]
    scope: Scope
    statements: dict[Statement, pd.DataFrame]


class CVMDatasetService:
    """Thin file-cache layer over the CVM Dados Abertos HTTP endpoints."""

    CACHE_TTL_HOURS = float(os.getenv("CVM_CACHE_TTL_HOURS", "24"))

    def __init__(
        self,
        request_manager: RequestManager | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.request_manager = request_manager or RequestManager()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dfp(self, year: int, scope: Scope = "con") -> CVMYearData | None:
        """Load annual standardized statements (DFP) for the requested year."""
        return self._load_year(doc_type="DFP", year=year, scope=scope)

    def get_itr(self, year: int, scope: Scope = "con") -> CVMYearData | None:
        """Load quarterly statements (ITR) for the requested year."""
        return self._load_year(doc_type="ITR", year=year, scope=scope)

    def get_cad(self) -> pd.DataFrame | None:
        """Load the company-registry CSV (CAD).

        Returns a DataFrame keyed by ``CD_CVM`` with one row per company.
        Columns include ``CNPJ_CIA``, ``DENOM_SOCIAL``, ``SIT`` (status), etc.
        """
        url = f"{_BASE}/CAD/DADOS/cad_cia_aberta.csv"
        cached = self._cached_path("cad_cia_aberta.csv")
        if not self._is_fresh(cached):
            content = self._download(url)
            if content is None:
                return None
            cached.write_bytes(content)
        try:
            df = pd.read_csv(cached, sep=";", encoding="latin-1", dtype=str)
        except Exception as exc:
            logger.error(f"CVMDatasetService: could not parse CAD CSV: {exc}")
            return None
        if "CD_CVM" in df.columns:
            df["CD_CVM"] = df["CD_CVM"].astype(str).str.strip()
        return df

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_year(
        self, *, doc_type: Literal["DFP", "ITR"], year: int, scope: Scope
    ) -> CVMYearData | None:
        zip_url = f"{_BASE}/DOC/{doc_type}/DADOS/{doc_type.lower()}_cia_aberta_{year}.zip"
        cached_zip = self._cached_path(f"{doc_type.lower()}_cia_aberta_{year}.zip")
        if not self._is_fresh(cached_zip):
            content = self._download(zip_url)
            if content is None:
                return None
            cached_zip.write_bytes(content)

        statements: dict[Statement, pd.DataFrame] = {}
        try:
            with zipfile.ZipFile(cached_zip, "r") as archive:
                for statement in ("BPA", "BPP", "DRE", "DFC_MD", "DFC_MI", "DMPL", "DVA"):
                    df = self._read_statement(archive, doc_type, statement, scope, year)
                    if df is not None:
                        statements[statement] = df  # type: ignore[index]
        except zipfile.BadZipFile:
            logger.error(
                f"CVMDatasetService: cached ZIP for {doc_type}/{year} is corrupt — re-downloading"
            )
            cached_zip.unlink(missing_ok=True)
            return None

        if not statements:
            logger.warning(f"CVMDatasetService: no parseable statements in {doc_type}/{year}")
            return None

        return CVMYearData(year=year, doc_type=doc_type, scope=scope, statements=statements)

    def _read_statement(
        self,
        archive: zipfile.ZipFile,
        doc_type: str,
        statement: str,
        scope: Scope,
        year: int,
    ) -> pd.DataFrame | None:
        """Load a single statement CSV from inside the year archive.

        CVM filenames follow the pattern
        ``{doc_type_lower}_cia_aberta_{statement}_{scope}_{year}.csv``.
        ITR DRE/DFC have ``DRE_con_{year}.csv`` directly.
        """
        candidate = f"{doc_type.lower()}_cia_aberta_{statement}_{scope}_{year}.csv"
        if candidate not in archive.namelist():
            return None
        try:
            with archive.open(candidate) as fh:
                df = pd.read_csv(
                    io.TextIOWrapper(fh, encoding="latin-1"),
                    sep=";",
                    dtype={"CD_CVM": str, "CD_CONTA": str},
                )
        except Exception as exc:
            logger.warning(
                f"CVMDatasetService: failed to parse {candidate} from {doc_type}/{year}: {exc}"
            )
            return None

        if df.empty:
            return None

        # Normalise the columns most downstream consumers depend on.
        if "CD_CVM" in df.columns:
            df["CD_CVM"] = df["CD_CVM"].astype(str).str.strip()
        if "DT_REFER" in df.columns:
            df["DT_REFER"] = pd.to_datetime(df["DT_REFER"], errors="coerce")
        if "VL_CONTA" in df.columns:
            df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
        return df

    # ------------------------------------------------------------------
    # File-cache helpers
    # ------------------------------------------------------------------

    def _cached_path(self, name: str) -> Path:
        return self.cache_dir / name

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours < self.CACHE_TTL_HOURS

    def _download(self, url: str) -> bytes | None:
        try:
            response = self.request_manager.get(url, timeout=120)
            response.raise_for_status()
        except Exception as exc:
            logger.warning(f"CVMDatasetService: failed to download {url}: {exc}")
            return None
        return response.content

    def purge_cache(self) -> None:
        """Wipe the on-disk cache (used in tests; not invoked by production code)."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
