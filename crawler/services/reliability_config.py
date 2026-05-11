"""
Reliability scoring configuration — pure Python, no project imports.

Perennial sectors: structurally resilient demand across economic cycles.
Cyclical sectors: heavy exposure to discretionary spend or commodity prices.
"""

CRITERION_WEIGHTS: dict[str, float] = {
    "profit_consistency": 0.35,
    "debt_control": 0.30,
    "tag_along": 0.20,
    "perennial_sector": 0.15,
}

# Upper-inclusive bands: score >= threshold → grade
GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "AAA"),
    (80, "AA"),
    (70, "A"),
    (55, "B"),
    (40, "C"),
    (0, "D"),
]

# B3 governance segment → TAG ALONG percentage
# Comparison uses .upper() — values stored by spiders may vary in case
TAG_ALONG_BY_SEGMENT: dict[str, int] = {
    "NM": 100,  # Novo Mercado
    "N2": 100,  # Nível 2
    "N1": 80,   # Nível 1
    "MA": 80,   # Mercado Ampliado / Tradicional
    "MB": 80,   # Mercado de Balcão
}
TAG_ALONG_DEFAULT: int = 80  # legal minimum when segment is null or unrecognised

# Perennial sector keyword matching — any substring match in sector.lower()
PERENNIAL_SECTOR_KEYWORDS: frozenset[str] = frozenset([
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
])

CYCLICAL_SECTOR_KEYWORDS: frozenset[str] = frozenset([
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
])
