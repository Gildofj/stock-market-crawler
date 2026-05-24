from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.models import Company
from core.models.schemas import CompanySchema

_PRESERVE_IF_NULL_FIELDS = frozenset(
    {
        "name",
        "sector",
        "sub_sector",
        "segment",
        "logo_url",
        "website",
        "cnpj",
        "cd_cvm",
        "asset_type",
        "underlying_ticker",
        "bdr_ratio",
    }
)


class CompanyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, company_id: uuid.UUID) -> Company | None:
        result = await self.db.execute(select(Company).filter(Company.id == company_id))
        return result.scalars().first()

    async def get_by_symbol(self, symbol: str) -> Company | None:
        result = await self.db.execute(select(Company).filter(Company.symbol == symbol))
        return result.scalars().first()

    async def get_taxonomy(self, symbol: str) -> dict[str, str | float | None] | None:
        """Returns cached asset taxonomy for a symbol (cd_cvm, asset_type, etc).

        Used by CrawlerEngine to short-circuit upstream lookups when the
        refresh_universe job has already cached the mapping.
        """
        stmt = select(
            Company.cnpj,
            Company.cd_cvm,
            Company.asset_type,
            Company.underlying_ticker,
            Company.bdr_ratio,
        ).filter(Company.symbol == symbol)
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return {
            "cnpj": row.cnpj,
            "cd_cvm": row.cd_cvm,
            "asset_type": row.asset_type,
            "underlying_ticker": row.underlying_ticker,
            "bdr_ratio": float(row.bdr_ratio) if row.bdr_ratio is not None else None,
        }

    async def get_many_by_symbols(self, symbols: list[str]) -> list[Company]:
        if not symbols:
            return []
        result = await self.db.execute(select(Company).filter(Company.symbol.in_(symbols)))
        return list(result.scalars().all())

    async def get_all_symbols(self) -> set[str]:
        result = await self.db.execute(select(Company.symbol))
        return set(result.scalars().all())

    async def get_existing_symbols(self, symbols: list[str]) -> set[str]:
        if not symbols:
            return set()
        result = await self.db.execute(select(Company.symbol).filter(Company.symbol.in_(symbols)))
        return set(result.scalars().all())

    async def list_paginated(self, skip: int = 0, limit: int = 1000) -> list[Company]:
        result = await self.db.execute(select(Company).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def search(self, query: str, limit: int = 10) -> list[Company]:
        is_postgres = self.db.bind.dialect.name == "postgresql"

        if is_postgres:
            stmt = (
                select(Company)
                .filter(
                    or_(
                        Company.symbol.ilike(f"%{query}%"),
                        Company.name.ilike(f"%{query}%"),
                        func.similarity(Company.symbol, query) > 0.3,
                        func.similarity(Company.name, query) > 0.3,
                    )
                )
                .order_by(
                    Company.symbol.ilike(query).desc(),
                    Company.symbol.ilike(f"%{query}%").desc(),
                    func.similarity(Company.name, query).desc(),
                )
                .limit(limit)
            )
        else:
            stmt = (
                select(Company)
                .filter(or_(Company.symbol.ilike(f"%{query}%"), Company.name.ilike(f"%{query}%")))
                .order_by(Company.symbol.ilike(query).desc(), Company.symbol.asc())
                .limit(limit)
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create(self, company_data: CompanySchema) -> Company:
        existing = await self.get_by_symbol(company_data.symbol)

        if existing is None:
            company = Company(**company_data.model_dump())
            self.db.add(company)
            await self.db.commit()
            await self.db.refresh(company)
            return company

        updated = False
        for field, value in company_data.model_dump(exclude_unset=True).items():
            if value is None and field in _PRESERVE_IF_NULL_FIELDS and getattr(existing, field):
                continue
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                updated = True
        if updated:
            await self.db.commit()
            await self.db.refresh(existing)
        return existing

    async def update_info(self, symbol: str, data: dict) -> None:
        company = await self.get_by_symbol(symbol)
        if company is None:
            return
        for key, value in data.items():
            setattr(company, key, value)
        await self.db.commit()
