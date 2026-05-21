"""Computes fundamental indicators from raw CVM open-data statements.

This spider is the replacement for every proprietary fundamentals scraper
that previously fed the ``Fundamental`` table. It reads the standardized
statements that every B3-listed company files with the CVM (DFP for annual,
ITR for quarterly), maps the universal account codes to line items, and
defers every formula to :mod:`core.services.financial_calculator`.

The line-item extraction is keyword + account-code resilient: CVM standard
codes are stable (e.g. ``3.01`` is always Revenue), but companies in
regulated industries (banks, insurers, utilities) sometimes shift codes by
one level. We use a primary code match, falling back to a regex over the
``DS_CONTA`` description for industry-agnostic robustness.

Market data (current price, shares outstanding) is *not* derived from CVM —
the spider expects it to be already populated on the ``CrawlResult`` by
the upstream B3 price spider. Price + shares are facts (Lei 9.610/98 Art. 8º)
that yfinance/B3 publish in real time.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from loguru import logger

from core.services.financial_calculator import RawFinancials, cagr, compute_all
from crawler.services.cvm_dataset_service import CVMDatasetService, CVMYearData, Statement

from ..models.contract import CrawlResult
from .base_spider import BaseSpider


@dataclass(frozen=True)
class _AccountSpec:
    """Locator for one line item: a primary CVM code + descriptive fallback regex."""

    statement: Statement
    code_prefix: str
    keywords: tuple[str, ...]


# The account-code prefixes follow CVM Manual de Normas Contábeis (CPC 26).
# Keywords are intentionally broad — they only fire as a fallback when the
# numeric code is not present (typical for banks/insurers that file the
# 4.x schedule instead of 3.x).
_REVENUE = _AccountSpec("DRE", "3.01", ("receita liquida", "receitas de intermedi"))
_GROSS_PROFIT = _AccountSpec("DRE", "3.03", ("resultado bruto",))
_EBIT = _AccountSpec("DRE", "3.05", ("resultado antes do resultado financeiro",))
_FINANCIAL_RESULT = _AccountSpec("DRE", "3.06", ("resultado financeiro",))
_PRETAX = _AccountSpec("DRE", "3.07", ("resultado antes dos tributos",))
_INCOME_TAX = _AccountSpec("DRE", "3.08", ("imposto de renda", "contribuicao social"))
_NET_INCOME = _AccountSpec(
    "DRE",
    "3.11",
    ("lucro/prejuizo consolidado", "lucro/prejuizo do periodo"),
)

_TOTAL_ASSETS = _AccountSpec("BPA", "1", ("ativo total",))
_CURRENT_ASSETS = _AccountSpec("BPA", "1.01", ("ativo circulante",))
_CASH = _AccountSpec("BPA", "1.01.01", ("caixa e equivalentes",))
_SHORT_TERM_INV = _AccountSpec("BPA", "1.01.02", ("aplicacoes financeiras",))

_CURRENT_LIABILITIES = _AccountSpec("BPP", "2.01", ("passivo circulante",))
_SHORT_TERM_DEBT = _AccountSpec("BPP", "2.01.04", ("emprestimos e financiamentos",))
_LONG_TERM_DEBT = _AccountSpec("BPP", "2.02.01", ("emprestimos e financiamentos",))
_EQUITY = _AccountSpec("BPP", "2.03", ("patrimonio liquido",))

# DFC line item for D&A (used to back EBITDA into EBIT + D&A when EBITDA is
# not published explicitly — most non-financial CVM filers report only EBIT).

# DFC_MI line for dividends and JCP paid to shareholders. Standard code
# 6.03.01 (Distribuição de dividendos). Banks/insurers occasionally file
# under 6.02.x — the fallback regex catches those plus JCP variants.
_DIVIDENDS_PAID = _AccountSpec(
    "DFC_MI",
    "6.03.01",
    ("dividendos pagos", "juros sobre capital proprio pagos", "jcp pagos"),
)

_DEPRECIATION_PATTERN = re.compile(r"deprecia|amortiza", re.IGNORECASE)


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def _derive_ebit(
    net_income: float | None,
    income_tax: float | None,
    pretax: float | None,
    financial_result: float | None,
) -> float | None:
    if financial_result is None:
        return None
    if pretax is not None:
        return pretax - financial_result
    if net_income is not None and income_tax is not None:
        return (net_income + income_tax) - financial_result
    return None


class CVMSpider(BaseSpider):
    """Spider that derives fundamentals from raw CVM Dados Abertos statements."""

    def __init__(
        self,
        dataset_service: CVMDatasetService | None = None,
        ticker_to_cvm_code: dict[str, str] | None = None,
    ) -> None:
        self.dataset_service = dataset_service or CVMDatasetService()
        self._ticker_index: dict[str, str] | None = ticker_to_cvm_code
        self._dfp_cache: dict[int, CVMYearData | None] = {}
        self._itr_cache: dict[int, CVMYearData | None] = {}

    # ------------------------------------------------------------------
    # BaseSpider contract
    # ------------------------------------------------------------------

    async def crawl_ticker(self, symbol: str) -> CrawlResult:
        result = CrawlResult(symbol=symbol)
        await asyncio.to_thread(self._populate_fundamentals, result)
        return result

    async def enrich(self, result: CrawlResult) -> None:
        """Compute fundamentals in-place using the spider's already-populated price data."""
        await asyncio.to_thread(self._populate_fundamentals, result)

    # ------------------------------------------------------------------
    # Core orchestration
    # ------------------------------------------------------------------

    def _populate_fundamentals(self, result: CrawlResult) -> None:
        cvm_code = self.get_cvm_code(result.symbol)
        if cvm_code is None:
            logger.warning(
                f"CVMSpider: no CD_CVM mapping for {result.symbol}; skipping fundamentals"
            )
            return

        latest_year = datetime.now().year
        raw = self._build_raw_financials(cvm_code, latest_year, result)
        if raw is None:
            return

        indicators = compute_all(raw)

        # CVM is the authoritative source for every numeric indicator. The B3
        # spider no longer writes these fields — it only feeds prices + shares.
        # Whatever yfinance reports lives separately in
        # `result.yahoo_info_indicators` and is later persisted by the
        # ReconciliationService for QA / ML drift modelling.
        result.p_l = indicators.p_l
        result.p_vp = indicators.p_vp
        result.ev_ebitda = indicators.ev_ebitda
        result.roe = indicators.roe
        result.roic = indicators.roic
        result.net_margin = indicators.net_margin
        # ``0.0`` preserves the historical semantics of "no dividends paid"
        # (distinct from "data missing"); downstream consumers rely on this
        # zero value, e.g. crawler_engine._calculate_advanced_metrics.
        result.dy = indicators.dy if indicators.dy is not None else 0.0
        result.liquid_debt_ebitda = indicators.net_debt_ebitda
        result.debt_to_equity = indicators.debt_to_equity
        result.market_cap = indicators.market_cap
        result.eps = indicators.eps
        result.valuation_graham = indicators.valuation_graham
        result.valuation_bazin = indicators.valuation_bazin

        # Growth metrics derived from a multi-year DFP window. Falling back to
        # None when CVM history is shorter than the requested window keeps
        # behaviour identical to the previous null-tolerant pipeline.
        result.cagr_revenue_5y = self._cagr_for(cvm_code, "DRE", _REVENUE, years=5)
        result.cagr_profit_5y = self._cagr_for(cvm_code, "DRE", _NET_INCOME, years=5)

    # ------------------------------------------------------------------
    # Ticker → CD_CVM resolution
    # ------------------------------------------------------------------

    def get_cvm_code(self, ticker: str) -> str | None:
        index = self._load_ticker_index()
        return index.get(ticker.upper())

    def _load_ticker_index(self) -> dict[str, str]:
        """Build a ticker → CD_CVM map from the CVM CAD registry, lazily.

        CAD doesn't carry the B3 ticker, so we approximate by stripping
        digits from the ticker and matching against ``DENOM_SOCIAL``. For the
        handful of tickers where the heuristic isn't reliable, callers can
        seed an explicit override at construction time.
        """
        if self._ticker_index is not None:
            return self._ticker_index
        cad = self.dataset_service.get_cad()
        if cad is None:
            self._ticker_index = {}
            return self._ticker_index

        from core.services.cnpj_map import CNPJ_TO_TICKER

        index: dict[str, str] = {}
        if "CNPJ_CIA" in cad.columns and "CD_CVM" in cad.columns:
            cad_normalised = cad.copy()
            cad_normalised["CNPJ_DIGITS"] = (
                cad_normalised["CNPJ_CIA"].fillna("").astype(str).str.replace(r"\D", "", regex=True)
            )
            for cnpj_digits, ticker in CNPJ_TO_TICKER.items():
                stripped = cnpj_digits.rstrip("A")
                hit = cad_normalised.loc[cad_normalised["CNPJ_DIGITS"] == stripped, "CD_CVM"]
                if not hit.empty:
                    index[ticker.upper()] = str(hit.iloc[0])

        self._ticker_index = index
        return index

    # ------------------------------------------------------------------
    # Raw-line-item extraction
    # ------------------------------------------------------------------

    def _get_year(self, doc_type: str, year: int) -> CVMYearData | None:
        cache = self._dfp_cache if doc_type == "DFP" else self._itr_cache
        if year not in cache:
            cache[year] = (
                self.dataset_service.get_dfp(year)
                if doc_type == "DFP"
                else self.dataset_service.get_itr(year)
            )
        return cache[year]

    def _build_raw_financials(
        self, cvm_code: str, year: int, result: CrawlResult
    ) -> RawFinancials | None:
        """Assemble the raw-line-item bag the calculator expects.

        Strategy:
        * Income-statement items prefer the latest ITR-derived trailing-twelve-months
          window. When ITR isn't available we fall back to the latest DFP annual.
        * Balance-sheet items use the latest available period (ITR or DFP).
        """
        dfp = None
        for offset in range(6):
            dfp = self._get_year("DFP", year - offset)
            if dfp is not None:
                break

        if dfp is None:
            logger.warning(
                f"CVMSpider: no DFP for {cvm_code} in the last 6 years (from {year}); "
                "skipping fundamentals"
            )
            return None

        annual_row = self._latest_annual_row(dfp, cvm_code)
        if annual_row is None:
            return None

        latest_price = result.prices[-1].close if result.prices else None
        # Prefer the documented yfinance get_shares_full() value supplied by
        # the B3 spider; fall back to inferring from market_cap when shares
        # are unavailable (e.g. yfinance outage).
        shares_outstanding = result.shares_outstanding or self._infer_shares(result)

        net_income = self._extract(dfp, cvm_code, _NET_INCOME, annual_row)
        income_tax = self._extract(dfp, cvm_code, _INCOME_TAX, annual_row)
        pretax = self._extract(dfp, cvm_code, _PRETAX, annual_row)
        financial_result = self._extract(dfp, cvm_code, _FINANCIAL_RESULT, annual_row)

        ebit = self._extract(dfp, cvm_code, _EBIT, annual_row)
        if ebit is None:
            ebit = _derive_ebit(net_income, income_tax, pretax, financial_result)

        depreciation = self._extract_depreciation(dfp, cvm_code, annual_row)
        ebitda = (ebit + depreciation) if (ebit is not None and depreciation is not None) else None

        dividends_raw = self._extract(dfp, cvm_code, _DIVIDENDS_PAID, annual_row)
        # DFC reports dividends as cash outflows (negative); the calculator
        # expects positive magnitude. TODO: aggregate the four most recent
        # ITRs for a true TTM window; using the latest DFP annual for now.
        dividends_paid_annual = abs(dividends_raw) if dividends_raw is not None else None

        return RawFinancials(
            revenue=self._extract(dfp, cvm_code, _REVENUE, annual_row),
            gross_profit=self._extract(dfp, cvm_code, _GROSS_PROFIT, annual_row),
            ebit=ebit,
            ebitda=ebitda,
            net_income=net_income,
            income_tax_expense=income_tax,
            pretax_income=pretax,
            financial_result=financial_result,
            total_assets=self._extract(dfp, cvm_code, _TOTAL_ASSETS, annual_row),
            current_assets=self._extract(dfp, cvm_code, _CURRENT_ASSETS, annual_row),
            cash_and_equivalents=self._extract(dfp, cvm_code, _CASH, annual_row),
            short_term_investments=self._extract(dfp, cvm_code, _SHORT_TERM_INV, annual_row),
            current_liabilities=self._extract(dfp, cvm_code, _CURRENT_LIABILITIES, annual_row),
            short_term_debt=self._extract(dfp, cvm_code, _SHORT_TERM_DEBT, annual_row),
            long_term_debt=self._extract(dfp, cvm_code, _LONG_TERM_DEBT, annual_row),
            equity=self._extract(dfp, cvm_code, _EQUITY, annual_row),
            dividends_paid_ttm=dividends_paid_annual,
            current_price=latest_price,
            shares_outstanding=shares_outstanding,
        )

    @staticmethod
    def _latest_annual_row(year_data: CVMYearData, cvm_code: str) -> datetime | None:
        """Return the most recent DT_REFER for a given company within the year package."""
        for df in year_data.statements.values():
            if "CD_CVM" not in df.columns or "DT_REFER" not in df.columns:
                continue
            slice_ = df.loc[df["CD_CVM"] == cvm_code, "DT_REFER"]
            if not slice_.empty:
                return slice_.max()
        return None

    def _extract(
        self,
        year_data: CVMYearData,
        cvm_code: str,
        spec: _AccountSpec,
        reference_date: datetime | None,
    ) -> float | None:
        df = year_data.statements.get(spec.statement)
        if df is None or reference_date is None:
            return None

        mask = (df["CD_CVM"] == cvm_code) & (df["DT_REFER"] == reference_date)
        if "CD_CONTA" in df.columns:
            mask &= df["CD_CONTA"].astype(str).str.startswith(spec.code_prefix + ".") | (
                df["CD_CONTA"].astype(str) == spec.code_prefix
            )

        slice_ = df.loc[mask]
        if slice_.empty and spec.keywords and "DS_CONTA" in df.columns:
            pattern = re.compile("|".join(re.escape(k) for k in spec.keywords), re.IGNORECASE)
            ds_normalised = df["DS_CONTA"].astype(str).map(_strip_accents).str.lower()
            fallback_mask = (
                (df["CD_CVM"] == cvm_code)
                & (df["DT_REFER"] == reference_date)
                & ds_normalised.str.contains(pattern, na=False)
            )
            slice_ = df.loc[fallback_mask]

        if slice_.empty:
            return None

        # Prefer the row whose CD_CONTA matches the spec prefix exactly (parent
        # row in the chart of accounts) over any sub-account that bubbled up
        # via the fallback regex.
        if "CD_CONTA" in slice_.columns:
            parent = slice_.loc[slice_["CD_CONTA"].astype(str) == spec.code_prefix]
            if not parent.empty:
                slice_ = parent

        value = slice_["VL_CONTA"].iloc[0]
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sum_keyword_leaves(
        year_data: CVMYearData,
        cvm_code: str,
        reference_date: datetime | None,
        statement: Statement,
        pattern: re.Pattern,
    ) -> float | None:
        df = year_data.statements.get(statement)
        if df is None or reference_date is None or "DS_CONTA" not in df.columns:
            return None

        ds_normalised = df["DS_CONTA"].astype(str).map(_strip_accents)
        mask = (
            (df["CD_CVM"] == cvm_code)
            & (df["DT_REFER"] == reference_date)
            & ds_normalised.str.contains(pattern, na=False)
        )
        matches = df.loc[mask]
        if matches.empty:
            return None

        leaves = matches
        if "CD_CONTA" in matches.columns:
            codes = matches["CD_CONTA"].astype(str).tolist()
            leaf_mask = (
                matches["CD_CONTA"]
                .astype(str)
                .apply(
                    lambda code: (
                        not any(other != code and other.startswith(code + ".") for other in codes)
                    )
                )
            )
            leaves = matches.loc[leaf_mask]

        values = leaves["VL_CONTA"].dropna()
        if values.empty:
            return None
        try:
            return float(values.sum())
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_depreciation(
        cls,
        year_data: CVMYearData,
        cvm_code: str,
        reference_date: datetime | None,
    ) -> float | None:
        dfc_value = cls._sum_keyword_leaves(
            year_data, cvm_code, reference_date, "DFC_MI", _DEPRECIATION_PATTERN
        )
        if dfc_value is not None:
            return dfc_value
        dre_value = cls._sum_keyword_leaves(
            year_data, cvm_code, reference_date, "DRE", _DEPRECIATION_PATTERN
        )
        if dre_value is not None:
            return abs(dre_value)
        return None

    @staticmethod
    def _infer_shares(result: CrawlResult) -> float | None:
        """Derive shares outstanding from already-populated market_cap and price."""
        if (
            result.market_cap is not None
            and result.prices
            and result.prices[-1].close is not None
            and result.prices[-1].close > 0
        ):
            return result.market_cap / result.prices[-1].close
        return None

    # ------------------------------------------------------------------
    # CAGR over multiple DFP years
    # ------------------------------------------------------------------

    def _cagr_for(
        self, cvm_code: str, statement: Statement, spec: _AccountSpec, years: int
    ) -> float | None:
        latest_year = datetime.now().year
        dfp = None
        for offset in range(6):
            dfp = self._get_year("DFP", latest_year - offset)
            if dfp is not None:
                break

        if dfp is None:
            return None

        end_year = dfp.year
        start_year = end_year - years

        end = self._annual_value(cvm_code, end_year, spec)
        start = self._annual_value(cvm_code, start_year, spec)
        return cagr(start, end, years)

    def _annual_value(self, cvm_code: str, year: int, spec: _AccountSpec) -> float | None:
        data = self._get_year("DFP", year)
        if data is None:
            return None
        ref_date = self._latest_annual_row(data, cvm_code)
        return self._extract(data, cvm_code, spec, ref_date)
