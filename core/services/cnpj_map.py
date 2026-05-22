TICKER_TO_CD_CVM: dict[str, str] = {
    "PETR4": "9512",
    "PETR3": "9512",
    "VALE3": "4170",
}


CNPJ_TO_TICKER: dict[str, str] = {
    "33000167000101": "PETR4",
    "33592510000154": "BBSE3",
    "00000000000191": "BBAS3",
    "60746948000112": "BBDC4",
    "76483817000120": "ITUB4",
    "92702067000196": "SANB11",
    "33611500000119": "BBDC3",
    "76535764000143": "B3SA3",
    "33113309000147": "VALE3",
    "60643228000121": "USIM5",
    "33256439000139": "CSNA3",
    "07526557000100": "GGBR4",
    "60872504000123": "ABEV3",
    "47508411000156": "WEGE3",
    "61584223000131": "EMBR3",
    "47960950000121": "MGLU3",
    "08540536000113": "BPAC11",
    "47866934000174": "EQTL3",
    "00833098000182": "CMIG4",
    "76483817000120A": "ITUB3",
    "33611500000119A": "BRFS3",
}


def resolve_ticker(cnpj: str) -> str | None:
    if not cnpj:
        return None
    digits = "".join(ch for ch in str(cnpj) if ch.isdigit())
    return CNPJ_TO_TICKER.get(digits)


def watched_cnpjs() -> set[str]:
    return {cnpj.rstrip("A") for cnpj in CNPJ_TO_TICKER}
