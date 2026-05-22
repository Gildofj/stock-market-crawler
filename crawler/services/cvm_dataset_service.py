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
    year: int
    doc_type: Literal["DFP", "ITR"]
    scope: Scope
    statements: dict[Statement, pd.DataFrame]


class CVMDatasetService:
    CACHE_TTL_HOURS = float(os.getenv("CVM_CACHE_TTL_HOURS", "24"))

    def __init__(
        self,
        request_manager: RequestManager | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.request_manager = request_manager or RequestManager()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_dfp(self, year: int, scope: Scope = "con") -> CVMYearData | None:
        return self._load_year(doc_type="DFP", year=year, scope=scope)

    def get_itr(self, year: int, scope: Scope = "con") -> CVMYearData | None:
        return self._load_year(doc_type="ITR", year=year, scope=scope)

    def get_cad(self) -> pd.DataFrame | None:
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

    def get_sector_by_cvm_code(self) -> dict[str, str]:
        cad = self.get_cad()
        if cad is None or "CD_CVM" not in cad.columns or "SETOR_ATIV" not in cad.columns:
            return {}
        mapping: dict[str, str] = {}
        for code, sector in zip(cad["CD_CVM"], cad["SETOR_ATIV"], strict=False):
            if not code or not sector or pd.isna(sector):
                continue
            mapping[str(code).strip()] = str(sector).strip()
        return mapping

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
                        statements[statement] = df  # type: ignore[index] - Motivo: DF dinâmico
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

        if "CD_CVM" in df.columns:
            df["CD_CVM"] = df["CD_CVM"].astype(str).str.strip()
        if "DT_REFER" in df.columns:
            df["DT_REFER"] = pd.to_datetime(df["DT_REFER"], errors="coerce")
        if "VL_CONTA" in df.columns:
            df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
        return df

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
            logger.error(
                f"CVMDatasetService: download_failed url={url} "
                f"error_type={type(exc).__name__} error={exc}"
            )
            return None
        return response.content

    def purge_cache(self) -> None:
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
