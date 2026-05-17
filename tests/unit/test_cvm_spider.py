"""Unit tests for the CVM spider — uses synthetic statement DataFrames to
exercise the account-code resolution and end-to-end indicator computation
without hitting the live CVM endpoints.
"""

from datetime import datetime

import pandas as pd

from crawler.models.contract import CrawlResult
from crawler.models.schemas import StockPriceSchema
from crawler.services.cvm_dataset_service import CVMYearData
from crawler.spiders.cvm_spider import CVMSpider

CVM_CODE = "00099"
REF_DATE = datetime(2024, 12, 31)


def _statement(code: str, description: str, value: float) -> dict:
    return {
        "CD_CVM": CVM_CODE,
        "CD_CONTA": code,
        "DS_CONTA": description,
        "DT_REFER": REF_DATE,
        "VL_CONTA": value,
    }


def _synthetic_year() -> CVMYearData:
    dre = pd.DataFrame(
        [
            _statement("3.01", "Receita de Venda de Bens e/ou Serviços", 1_000.0),
            _statement("3.03", "Resultado Bruto", 400.0),
            _statement("3.05", "Resultado Antes do Resultado Financeiro e dos Tributos", 250.0),
            _statement("3.07", "Resultado Antes dos Tributos sobre o Lucro", 200.0),
            _statement("3.08", "Imposto de Renda e Contribuição Social", 50.0),
            _statement("3.11", "Lucro/Prejuízo Consolidado do Período", 150.0),
        ]
    )
    bpa = pd.DataFrame(
        [
            _statement("1", "Ativo Total", 2_000.0),
            _statement("1.01", "Ativo Circulante", 600.0),
            _statement("1.01.01", "Caixa e Equivalentes de Caixa", 100.0),
            _statement("1.01.02", "Aplicações Financeiras", 50.0),
        ]
    )
    bpp = pd.DataFrame(
        [
            _statement("2.01", "Passivo Circulante", 300.0),
            _statement("2.01.04", "Empréstimos e Financiamentos", 80.0),
            _statement("2.02.01", "Empréstimos e Financiamentos", 220.0),
            _statement("2.03", "Patrimônio Líquido Consolidado", 1_000.0),
        ]
    )
    dfc = pd.DataFrame(
        [_statement("6.01.01", "Depreciação e Amortização", 50.0)],
    )
    return CVMYearData(
        year=2024,
        doc_type="DFP",
        scope="con",
        statements={"DRE": dre, "BPA": bpa, "BPP": bpp, "DFC_MI": dfc},
    )


def _spider() -> CVMSpider:
    spider = CVMSpider(ticker_to_cvm_code={"FLOW3": CVM_CODE})
    year_data = _synthetic_year()
    # Pre-populate the year cache so the spider doesn't try to hit the network.
    spider._dfp_cache[datetime.now().year] = year_data
    spider._dfp_cache[datetime.now().year - 1] = year_data
    return spider


def _result_with_price() -> CrawlResult:
    return CrawlResult(
        symbol="FLOW3",
        market_cap=2_000.0,
        prices=[StockPriceSchema(time=REF_DATE, close=20.0, volume=1000)],
    )


def test_cvm_spider_populates_universal_indicators():
    spider = _spider()
    result = _result_with_price()

    spider.enrich(result)

    # shares = market_cap / price = 100
    # EPS = 150 / 100 = 1.5; P/L = 20 / 1.5
    assert result.eps == 1.5
    assert result.p_l is not None and result.p_l > 0
    # BVPS = 1000 / 100 = 10; P/VP = 2
    assert result.p_vp == 2.0
    # ROE = 150 / 1000 = 15%
    assert result.roe == 15.0
    # Net margin = 150 / 1000 = 15%
    assert result.net_margin == 15.0
    # Net debt / EBITDA = (300 - 150) / (250 + 50) = 0.5
    assert result.liquid_debt_ebitda == 0.5
    # Debt/Equity = 300/1000 = 0.3
    assert result.debt_to_equity == 0.3


def test_cvm_spider_skips_when_mapping_missing():
    spider = CVMSpider(ticker_to_cvm_code={})
    result = _result_with_price()
    spider.enrich(result)
    assert result.p_l is None
    assert result.roe is None


def test_cvm_spider_does_not_clobber_preexisting_values():
    spider = _spider()
    result = _result_with_price()
    result.p_l = 99.0  # pre-populated by an earlier stage
    spider.enrich(result)
    assert result.p_l == 99.0  # untouched
    assert result.roe is not None  # other fields still computed
