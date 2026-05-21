from __future__ import annotations

from typing import TypedDict


class MetadataOverride(TypedDict, total=False):
    sector: str
    sub_sector: str
    segment: str
    logo_url: str


_OVERRIDES: dict[str, MetadataOverride] = {
    "BOVA11": {"sector": "Financial Services", "sub_sector": "ETF", "segment": "Ibovespa Index"},
    "IVVB11": {"sector": "Financial Services", "sub_sector": "ETF", "segment": "S&P 500 Index"},
    "SMAL11": {"sector": "Financial Services", "sub_sector": "ETF", "segment": "Small Caps Index"},
    "DIVO11": {"sector": "Financial Services", "sub_sector": "ETF", "segment": "Dividend Index"},
    "HGLG11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Logistics"},
    "HGRE11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Offices"},
    "HGRU11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Retail"},
    "KNRI11": {
        "sector": "Real Estate",
        "sub_sector": "REIT",
        "segment": "Offices and Logistics",
    },
    "MXRF11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Receivables"},
    "XPLG11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Logistics"},
    "XPML11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Shopping Malls"},
    "VISC11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Shopping Malls"},
    "BCFF11": {"sector": "Real Estate", "sub_sector": "REIT", "segment": "Fund of Funds"},
    "AAPL34": {
        "sector": "Technology",
        "sub_sector": "Consumer Electronics",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/apple.com",
    },
    "MSFT34": {
        "sector": "Technology",
        "sub_sector": "Software",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/microsoft.com",
    },
    "GOGL34": {
        "sector": "Communication Services",
        "sub_sector": "Internet Content",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/abc.xyz",
    },
    "AMZO34": {
        "sector": "Consumer Cyclical",
        "sub_sector": "Internet Retail",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/amazon.com",
    },
    "TSLA34": {
        "sector": "Consumer Cyclical",
        "sub_sector": "Auto Manufacturers",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/tesla.com",
    },
    "NVDC34": {
        "sector": "Technology",
        "sub_sector": "Semiconductors",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/nvidia.com",
    },
    "M1TA34": {
        "sector": "Communication Services",
        "sub_sector": "Internet Content",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/meta.com",
    },
    "NFLX34": {
        "sector": "Communication Services",
        "sub_sector": "Entertainment",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/netflix.com",
    },
    "DISB34": {
        "sector": "Communication Services",
        "sub_sector": "Entertainment",
        "segment": "BDR",
        "logo_url": "https://logo.clearbit.com/disney.com",
    },
}


def get_override(symbol: str) -> MetadataOverride:
    return _OVERRIDES.get(symbol.upper(), {})
