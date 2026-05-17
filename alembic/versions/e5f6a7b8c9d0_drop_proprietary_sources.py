"""drop_proprietary_sources

Removes the proprietary fundamentals sources (Fundamentus, StatusInvest)
from the ``data_sources`` registry now that the crawler pipeline derives
every indicator locally from CVM open data + B3 prices. Adds a ``b3`` row
for the B3 instruments CSV used by ``TickerService`` to discover the
ticker universe.

The proprietary rows are deleted unconditionally; downgrade re-seeds them
in case a deployment needs to roll back to a previous build that still
referenced their FKs (the SET NULL FK keeps existing rows intact either
way).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-17 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM data_sources
         WHERE slug IN ('fundamentus', 'statusinvest')
        """
    )

    op.execute(
        """
        INSERT INTO data_sources
            (slug, display_name, homepage_url, tos_url, license_label, legal_basis, risk_tier)
        VALUES
            ('b3', 'B3 — Brasil, Bolsa, Balcão',
             'https://www.b3.com.br/',
             'https://www.b3.com.br/pt_br/solucoes/plataformas/puma-trading-system/'
             'para-desenvolvedores-e-vendors/dados-publicos/',
             'public-domain',
             'Arquivos publicos B3 (instrumentos, COTAHIST, comunicados). '
             'Politica de dados publicos da B3.',
             'low')
        ON CONFLICT (slug) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM data_sources WHERE slug = 'b3'")
    op.execute(
        """
        INSERT INTO data_sources
            (slug, display_name, homepage_url, tos_url, license_label, legal_basis, risk_tier)
        VALUES
            ('fundamentus', 'Fundamentus',
             'https://www.fundamentus.com.br/', NULL,
             'tos-restricted',
             'Indicadores fundamentalistas (fatos numericos). '
             'ToS do site pode restringir acesso programatico.',
             'medium'),
            ('statusinvest', 'StatusInvest',
             'https://statusinvest.com.br/',
             'https://statusinvest.com.br/termos-de-uso',
             'tos-restricted',
             'Indicadores fundamentalistas (fatos numericos). '
             'ToS do site pode restringir acesso programatico.',
             'high')
        ON CONFLICT (slug) DO NOTHING
        """
    )
