CRITERION_WEIGHTS: dict[str, float] = {
    "profit_consistency": 0.35,
    "debt_control": 0.30,
    "tag_along": 0.20,
    "perennial_sector": 0.15,
}

GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "AAA"),
    (80, "AA"),
    (70, "A"),
    (55, "B"),
    (40, "C"),
    (0, "D"),
]

TAG_ALONG_BY_SEGMENT: dict[str, int] = {
    "NM": 100,
    "N2": 100,
    "N1": 80,
    "MA": 80,
    "MB": 80,
}
TAG_ALONG_DEFAULT: int = 80

PERENNIAL_SECTOR_KEYWORDS: frozenset[str] = frozenset(
    [
        "utilities",
        "electric",
        "energia",
        "eletric",
        "saneamento",
        "água",
        "water",
        "gás",
        "gas",
        "alimentos",
        "food",
        "bebidas",
        "beverage",
        "consumo não cíclico",
        "consumer staples",
        "saúde",
        "health",
        "farmacêutico",
        "pharmaceutical",
        "telecomunicações",
        "telecommunication",
        "telecom",
        "petróleo",
        "oil",
        "petro",
        "seguros",
        "insurance",
    ]
)

CYCLICAL_SECTOR_KEYWORDS: frozenset[str] = frozenset(
    [
        "varejo",
        "retail",
        "consumo cíclico",
        "consumer discretionary",
        "construção",
        "construction",
        "real estate",
        "imóveis",
        "turismo",
        "tourism",
        "aviação",
        "airlines",
        "automóvel",
        "automobile",
        "mineração",
        "mining",
        "siderurgia",
        "steel",
    ]
)
