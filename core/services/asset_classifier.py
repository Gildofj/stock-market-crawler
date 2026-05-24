"""Asset-type classifier shared by every spider, refresh task, and ticker
service.

The classification is hybrid: a third-party source's `quoteType` (when
available) disambiguates suffix 11 between FII / ETF / UNIT (e.g. BOVA11 is an
ETF, MXRF11 is a FII), but the B3 suffix is authoritative for BDRs and most
equities since upstream sources often tag BDRs as plain EQUITY.
"""

from __future__ import annotations


def classify_asset_type(*, quote_type: str | None, symbol: str) -> str:
    """Return one of: ``EQUITY | FII | BDR | ETF | UNIT``.

    Order of precedence:
        1. ``quote_type == "ETF"`` → ETF (suffix 11 is ambiguous; trust the
           explicit hint when present).
        2. B3 suffix rules — 11→FII, 32/33/34/35→BDR.
        3. ``quote_type == "MUTUALFUND"`` → FII (fallback for non-11 funds).
        4. Default EQUITY (ON/PN/PNA/PNB tickers ending 3/4/5/6).

    Fractional suffix ``F`` is stripped before evaluation.
    """
    qt = (quote_type or "").upper()
    if qt == "ETF":
        return "ETF"

    cleaned = symbol.upper().replace(".SA", "").rstrip("F")
    if cleaned.endswith("11"):
        return "FII"
    if cleaned.endswith(("32", "33", "34", "35")):
        return "BDR"
    if qt == "MUTUALFUND":
        return "FII"
    return "EQUITY"
