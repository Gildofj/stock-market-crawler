from datetime import datetime
from typing import cast

import pandas as pd

from crawler.services.cvm_dataset_service import CVMYearData, Statement
from crawler.spiders.cvm_spider import CVMSpider, _strip_accents

CVM_CODE = "00099"
REF_DATE = datetime(2024, 12, 31)


def _row(code: str, description: str, value: float) -> dict:
    return {
        "CD_CVM": CVM_CODE,
        "CD_CONTA": code,
        "DS_CONTA": description,
        "DT_REFER": REF_DATE,
        "VL_CONTA": value,
    }


def _year(statements: dict[str, list[dict]]) -> CVMYearData:
    return CVMYearData(
        year=2024,
        doc_type="DFP",
        scope="con",
        statements={cast(Statement, name): pd.DataFrame(rows) for name, rows in statements.items()},
    )


def test_strip_accents_handles_portuguese_letters():
    assert _strip_accents("Depreciação e Amortização") == "Depreciacao e Amortizacao"
    assert _strip_accents("PROVISÕES") == "PROVISOES"
    assert _strip_accents("plain") == "plain"


def test_dfc_grouped_layout_at_6_01_01_02():
    year = _year(
        {
            "DFC_MI": [
                _row("6.01.01", "Caixa Gerado nas Operações", 800.0),
                _row("6.01.01.01", "Lucro Líquido do Exercício", 500.0),
                _row("6.01.01.02", "Depreciação e Amortização", 200.0),
                _row("6.01.01.03", "Provisões diversas", 100.0),
            ]
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 200.0


def test_dfc_flat_layout_at_6_01_02():
    year = _year(
        {
            "DFC_MI": [
                _row("6.01.01", "Lucro Líquido do Exercício", 500.0),
                _row("6.01.02", "Depreciações e Amortizações", 180.0),
                _row("6.01.03", "Provisões", 60.0),
            ]
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 180.0


def test_dfc_sums_separate_depreciation_and_amortization_lines():
    year = _year(
        {
            "DFC_MI": [
                _row("6.01.02", "Depreciações", 120.0),
                _row("6.01.03", "Amortizações", 30.0),
            ]
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 150.0


def test_dfc_prefers_leaves_over_parent_when_both_match():
    year = _year(
        {
            "DFC_MI": [
                _row("6.01.02", "Ajustes - Depreciação e Amortização", 999.0),
                _row("6.01.02.01", "Depreciação", 70.0),
                _row("6.01.02.02", "Amortização", 30.0),
            ]
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 100.0


def test_dre_fallback_when_dfc_has_no_depreciation_line():
    year = _year(
        {
            "DFC_MI": [
                _row("6.01.01", "Lucro Líquido", 500.0),
                _row("6.01.02", "Provisões", 80.0),
            ],
            "DRE": [
                _row("3.01", "Receita", 1_000.0),
                _row("3.04.02", "Depreciação e Amortização", -150.0),
            ],
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 150.0


def test_dre_fallback_sums_depreciation_split_across_cogs_and_sga():
    year = _year(
        {
            "DFC_MI": [_row("6.01.01", "Lucro Líquido", 500.0)],
            "DRE": [
                _row("3.02.01", "Depreciação alocada ao CMV", -90.0),
                _row("3.04.02", "Amortização operacional", -40.0),
            ],
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 130.0


def test_dfc_wins_over_dre_when_both_have_depreciation():
    year = _year(
        {
            "DFC_MI": [_row("6.01.02", "Depreciação e Amortização", 200.0)],
            "DRE": [_row("3.04.02", "Depreciação", -999.0)],
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 200.0


def test_returns_none_when_neither_statement_has_depreciation():
    year = _year(
        {
            "DFC_MI": [_row("6.01.01", "Lucro Líquido", 500.0)],
            "DRE": [_row("3.01", "Receita", 1_000.0)],
        }
    )
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) is None


def test_ignores_other_companies():
    rows = [
        _row("6.01.02", "Depreciação e Amortização", 200.0),
        {**_row("6.01.02", "Depreciação e Amortização", 999.0), "CD_CVM": "OTHER"},
    ]
    year = _year({"DFC_MI": rows})
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) == 200.0


def test_returns_none_when_both_statements_missing():
    year = CVMYearData(year=2024, doc_type="DFP", scope="con", statements={})
    assert CVMSpider._extract_depreciation(year, CVM_CODE, REF_DATE) is None
