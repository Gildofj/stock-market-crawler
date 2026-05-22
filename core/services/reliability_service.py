import uuid

import yfinance as yf
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from core.models.models import Company, CompanyReliability, Fundamental
from core.services.reliability_config import (
    CRITERION_WEIGHTS,
    CYCLICAL_SECTOR_KEYWORDS,
    GRADE_THRESHOLDS,
    PERENNIAL_SECTOR_KEYWORDS,
    TAG_ALONG_BY_SEGMENT,
    TAG_ALONG_DEFAULT,
)


class ReliabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def compute_and_save(self, company_id: uuid.UUID) -> CompanyReliability | None:
        stmt_company = select(Company).filter(Company.id == company_id)
        result_company = await self.db.execute(stmt_company)
        company = result_company.scalars().first()

        if not company:
            logger.warning(f"ReliabilityService: company {company_id} not found")
            return None

        symbol = str(company.symbol)
        logger.info(f"ReliabilityService: computing reliability for {symbol}")

        profitable_years, max_years = self._fetch_profit_history(symbol)
        debt_compliant, debt_total = await self._query_debt_history(company_id)
        tag_along_pct = self._derive_tag_along(str(company.segment) if company.segment else None)
        is_perennial = self._classify_sector(str(company.sector) if company.sector else None)

        profit_score = await self._score_profit_consistency(profitable_years, max_years, company_id)
        debt_score = await self._score_debt_control(debt_compliant, debt_total, company_id)
        tag_score = self._score_tag_along(tag_along_pct)
        perennial_score = self._score_perennial(is_perennial)

        reliability_score = round(
            profit_score * CRITERION_WEIGHTS["profit_consistency"]
            + debt_score * CRITERION_WEIGHTS["debt_control"]
            + tag_score * CRITERION_WEIGHTS["tag_along"]
            + perennial_score * CRITERION_WEIGHTS["perennial_sector"]
        )
        reliability_grade = self._score_to_grade(reliability_score)

        return await self._upsert(
            company_id=company_id,
            profit_consistency_score=profit_score,
            debt_control_score=debt_score,
            tag_along_score=tag_score,
            perennial_sector_score=perennial_score,
            profitable_years_verified=profitable_years,
            max_years_available=max_years,
            debt_snapshots_compliant=debt_compliant,
            debt_snapshots_total=debt_total,
            tag_along_pct=tag_along_pct,
            is_perennial_sector=is_perennial,
            reliability_score=reliability_score,
            reliability_grade=reliability_grade,
        )

    def _fetch_profit_history(self, symbol: str) -> tuple[int, int]:
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        try:
            ticker = yf.Ticker(yf_symbol)
            stmt = ticker.income_stmt
            if stmt is None or stmt.empty:
                return 0, 0

            net_income_row = None
            for label in stmt.index:
                if "net income" in str(label).lower():
                    net_income_row = stmt.loc[label]
                    break

            if net_income_row is None:
                return 0, 0

            values = [v for v in net_income_row.values if v is not None]
            max_years = len(values)
            profitable = sum(1 for v in values if float(v) > 0)
            return profitable, max_years
        except Exception as exc:
            logger.warning(f"ReliabilityService: yfinance income_stmt failed for {symbol}: {exc}")
            return 0, 0

    async def _query_debt_history(self, company_id: uuid.UUID) -> tuple[int, int]:
        stmt = (
            select(Fundamental.liquid_debt_ebitda)
            .filter(Fundamental.company_id == company_id)
            .filter(Fundamental.liquid_debt_ebitda.isnot(None))
        )
        result = await self.db.execute(stmt)
        records = result.all()

        total = len(records)
        if total == 0:
            return 0, 0
        compliant = sum(1 for (v,) in records if float(v) <= 2.0)
        return compliant, total

    def _derive_tag_along(self, segment: str | None) -> int:
        if not segment:
            return TAG_ALONG_DEFAULT
        return TAG_ALONG_BY_SEGMENT.get(segment.strip().upper(), TAG_ALONG_DEFAULT)

    def _classify_sector(self, sector: str | None) -> bool | None:
        if not sector:
            return None
        sector_lower = sector.lower()
        for kw in PERENNIAL_SECTOR_KEYWORDS:
            if kw in sector_lower:
                return True
        for kw in CYCLICAL_SECTOR_KEYWORDS:
            if kw in sector_lower:
                return False
        return None

    async def _score_profit_consistency(
        self,
        profitable_years: int,
        max_years: int,
        company_id: uuid.UUID,
    ) -> int:
        if max_years == 0:
            return 0

        base = round((profitable_years / max_years) * 80)

        stmt = (
            select(Fundamental.cagr_profit_5y)
            .filter(Fundamental.company_id == company_id)
            .filter(Fundamental.cagr_profit_5y.isnot(None))
            .order_by(Fundamental.collected_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        latest_cagr = result.scalars().first()

        bonus = 20 if (latest_cagr and float(latest_cagr) > 0) else 0

        return min(base + bonus, 100)

    async def _score_debt_control(
        self,
        compliant_snapshots: int,
        total_snapshots: int,
        company_id: uuid.UUID,
    ) -> int:
        stmt = (
            select(Fundamental.liquid_debt_ebitda)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        current_ratio = result.scalars().first()

        if current_ratio is None:
            return 50

        ratio = float(current_ratio)
        if ratio <= 2.0:
            base = 80
        elif ratio <= 3.5:
            base = 40
        else:
            base = 0

        bonus = round((compliant_snapshots / total_snapshots) * 20) if total_snapshots >= 2 else 0

        return min(base + bonus, 100)

    def _score_tag_along(self, tag_along_pct: int) -> int:
        if tag_along_pct >= 100:
            return 100
        if tag_along_pct >= 80:
            return 50
        return 0

    def _score_perennial(self, is_perennial: bool | None) -> int:
        if is_perennial is True:
            return 100
        if is_perennial is None:
            return 50
        return 0

    def _score_to_grade(self, score: int) -> str:
        for threshold, grade in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "D"

    async def _upsert(self, company_id: uuid.UUID, **fields: object) -> CompanyReliability | None:
        stmt = select(CompanyReliability).filter(CompanyReliability.company_id == company_id)
        result = await self.db.execute(stmt)
        record = result.scalars().first()

        if record:
            for key, value in fields.items():
                setattr(record, key, value)
        else:
            record = CompanyReliability(company_id=company_id, **fields)
            self.db.add(record)

        try:
            await self.db.commit()
            await self.db.refresh(record)
            logger.success(
                f"ReliabilityService: saved score={fields.get('reliability_score')} "
                f"grade={fields.get('reliability_grade')} for company_id={company_id}"
            )
            return record
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"ReliabilityService: failed to save for {company_id}: {exc}")
            raise DatabaseError("Failed to persist reliability score") from exc
