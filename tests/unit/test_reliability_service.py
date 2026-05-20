import uuid

import pytest

from core.services.reliability_service import ReliabilityService


@pytest.fixture
def service(mocker):
    mock_db = mocker.Mock()
    # Mock AsyncSession methods
    mock_db.execute = mocker.AsyncMock()
    mock_db.commit = mocker.AsyncMock()
    mock_db.rollback = mocker.AsyncMock()
    mock_db.refresh = mocker.AsyncMock()
    return ReliabilityService(db=mock_db)


# --- Tag Along derivation ---


def test_derive_tag_along_novo_mercado(service):
    assert service._derive_tag_along("NM") == 100


def test_derive_tag_along_n2(service):
    assert service._derive_tag_along("N2") == 100


def test_derive_tag_along_n1(service):
    assert service._derive_tag_along("N1") == 80


def test_derive_tag_along_null(service):
    assert service._derive_tag_along(None) == 80


def test_derive_tag_along_unknown_segment(service):
    assert service._derive_tag_along("EQUITY") == 80


def test_derive_tag_along_case_insensitive(service):
    assert service._derive_tag_along("nm") == 100


# --- Sector classification ---


def test_classify_sector_perennial_utilities(service):
    assert service._classify_sector("Utilities") is True


def test_classify_sector_perennial_saude(service):
    assert service._classify_sector("Saúde") is True


def test_classify_sector_perennial_energia(service):
    assert service._classify_sector("Energia Elétrica") is True


def test_classify_sector_perennial_telecom(service):
    assert service._classify_sector("Telecomunicações") is True


def test_classify_sector_cyclical_varejo(service):
    assert service._classify_sector("Varejo") is False


def test_classify_sector_cyclical_construction(service):
    assert service._classify_sector("Construção Civil") is False


def test_classify_sector_unknown(service):
    assert service._classify_sector("Tecnologia") is None


def test_classify_sector_none(service):
    assert service._classify_sector(None) is None


# --- Score: tag along ---


def test_score_tag_along_full(service):
    assert service._score_tag_along(100) == 100


def test_score_tag_along_partial(service):
    assert service._score_tag_along(80) == 50


def test_score_tag_along_below_minimum(service):
    assert service._score_tag_along(50) == 0


# --- Score: perennial ---


def test_score_perennial_true(service):
    assert service._score_perennial(True) == 100


def test_score_perennial_none(service):
    assert service._score_perennial(None) == 50


def test_score_perennial_false(service):
    assert service._score_perennial(False) == 0


# --- Score: grade thresholds ---


@pytest.mark.parametrize(
    "score,expected_grade",
    [
        (95, "AAA"),
        (90, "AAA"),
        (85, "AA"),
        (80, "AA"),
        (72, "A"),
        (70, "A"),
        (60, "B"),
        (55, "B"),
        (45, "C"),
        (40, "C"),
        (20, "D"),
        (0, "D"),
    ],
)
def test_score_to_grade_thresholds(service, score, expected_grade):
    assert service._score_to_grade(score) == expected_grade


# --- Score: profit consistency ---


@pytest.mark.asyncio
async def test_score_profit_no_data(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = None
    service.db.execute.return_value = mock_result

    result = await service._score_profit_consistency(0, 0, uuid.uuid4())
    assert result == 0


@pytest.mark.asyncio
async def test_score_profit_all_profitable_positive_cagr(service, mocker):
    mock_result = mocker.Mock()
    # scalars().first() returns the column value (float)
    mock_result.scalars.return_value.first.return_value = 12.5
    service.db.execute.return_value = mock_result

    result = await service._score_profit_consistency(4, 4, uuid.uuid4())
    assert result == 100  # base=80 + bonus=20


@pytest.mark.asyncio
async def test_score_profit_all_profitable_negative_cagr(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = -2.0
    service.db.execute.return_value = mock_result

    result = await service._score_profit_consistency(4, 4, uuid.uuid4())
    assert result == 80  # base=80, no bonus


@pytest.mark.asyncio
async def test_score_profit_partial_years(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = 5.0
    service.db.execute.return_value = mock_result

    result = await service._score_profit_consistency(3, 4, uuid.uuid4())
    assert result == min(round((3 / 4) * 80) + 20, 100)


# --- Score: debt control ---


@pytest.mark.asyncio
async def test_score_debt_compliant_no_history(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = 1.5
    service.db.execute.return_value = mock_result

    result = await service._score_debt_control(0, 0, uuid.uuid4())
    assert result == 80  # base=80, no history bonus


@pytest.mark.asyncio
async def test_score_debt_high(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = 4.0
    service.db.execute.return_value = mock_result

    result = await service._score_debt_control(0, 0, uuid.uuid4())
    assert result == 0


@pytest.mark.asyncio
async def test_score_debt_moderate(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = 3.0
    service.db.execute.return_value = mock_result

    result = await service._score_debt_control(0, 1, uuid.uuid4())
    assert result == 40


@pytest.mark.asyncio
async def test_score_debt_with_history_bonus(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = 1.5
    service.db.execute.return_value = mock_result

    # 3 out of 4 snapshots compliant → bonus = round(3/4 * 20) = 15
    result = await service._score_debt_control(3, 4, uuid.uuid4())
    assert result == 95  # 80 + 15


@pytest.mark.asyncio
async def test_score_debt_null_returns_neutral(service, mocker):
    mock_result = mocker.Mock()
    mock_result.scalars.return_value.first.return_value = None
    service.db.execute.return_value = mock_result

    result = await service._score_debt_control(0, 0, uuid.uuid4())
    assert result == 50


# --- Composite weighted score ---


def test_compute_composite_weighted():
    """Validates the composite formula independently of DB calls."""
    from core.services.reliability_config import CRITERION_WEIGHTS

    profit, debt, tag, perennial = 80, 80, 100, 100
    expected = round(
        profit * CRITERION_WEIGHTS["profit_consistency"]
        + debt * CRITERION_WEIGHTS["debt_control"]
        + tag * CRITERION_WEIGHTS["tag_along"]
        + perennial * CRITERION_WEIGHTS["perennial_sector"]
    )
    assert expected == 87
