"""add_data_sources_registry

Adds the canonical ``data_sources`` registry plus nullable provenance FKs on
the tables that persist third-party data. The columns are all nullable on
purpose — legacy rows are left intact, and a separate backfill script
(``scripts/backfill_data_sources.py``) populates them when run by the
operator.

A small seed for the 9 known sources is inserted in the same revision so the
``SourceRegistry`` singleton has something to look up immediately after the
migration is applied. The seed uses ``ON CONFLICT DO NOTHING`` so re-running
is safe.

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-17 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS data_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug VARCHAR(50) NOT NULL UNIQUE,
            display_name VARCHAR(120) NOT NULL,
            homepage_url VARCHAR(500) NOT NULL,
            tos_url VARCHAR(500),
            license_label VARCHAR(60),
            legal_basis TEXT,
            contact_email VARCHAR(255),
            risk_tier VARCHAR(10) NOT NULL DEFAULT 'medium',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            last_reviewed_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_sources_slug ON data_sources(slug)")

    op.execute("""
        ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS metadata_source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE stock_prices
            ADD COLUMN IF NOT EXISTS source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE fundamentals
            ADD COLUMN IF NOT EXISTS primary_source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS contributing_sources JSON
    """)
    op.execute("""
        ALTER TABLE lake_news
            ADD COLUMN IF NOT EXISTS source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE lake_ri_documents
            ADD COLUMN IF NOT EXISTS source_id UUID
                REFERENCES data_sources(id) ON DELETE SET NULL
    """)

    # Seed the canonical sources. ON CONFLICT DO NOTHING makes the migration
    # idempotent when re-applied (downgrade + upgrade keeps the data).
    op.execute("""
        INSERT INTO data_sources
            (slug, display_name, homepage_url, tos_url, license_label, legal_basis, risk_tier)
        VALUES
            ('cvm', 'Comissão de Valores Mobiliários',
             'https://dados.cvm.gov.br/', NULL,
             'public-domain',
             'Atos oficiais — Lei 9.610/98 Art. 8º IV; dados abertos sob Lei 12.527/2011 (LAI).',
             'low'),
            ('bcb', 'Banco Central do Brasil',
             'https://dadosabertos.bcb.gov.br/', 'https://dadosabertos.bcb.gov.br/dataset',
             'public-domain',
             'Dados macroeconômicos sob política de dados abertos do BCB.',
             'low'),
            ('infomoney', 'InfoMoney',
             'https://www.infomoney.com.br/', 'https://www.infomoney.com.br/termos-de-uso/',
             'rss-fair-use',
             'RSS público; armazena apenas título + summary publicado pelo feed + URL original.',
             'medium'),
            ('valor', 'Valor Econômico',
             'https://valor.globo.com/', 'https://valor.globo.com/termos-de-uso/',
             'rss-fair-use',
             'RSS público; armazena apenas título + summary publicado pelo feed + URL original.',
             'medium'),
            ('investing', 'Investing.com Brasil',
             'https://br.investing.com/', 'https://br.investing.com/about-us/terms-and-conditions',
             'rss-fair-use',
             'RSS público; armazena apenas título + summary publicado pelo feed + URL original.',
             'medium'),
            ('money_times', 'Money Times',
             'https://www.moneytimes.com.br/', 'https://www.moneytimes.com.br/termos-de-uso/',
             'rss-fair-use',
             'RSS público; armazena apenas título + summary publicado pelo feed + URL original.',
             'medium'),
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
             'high'),
            ('yfinance', 'Yahoo Finance (via yfinance)',
             'https://finance.yahoo.com/',
             'https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html',
             'tos-restricted',
             'Cotacoes historicas e fundamentos. ToS do Yahoo '
             'restringe redistribuicao; uso domestico/educacional comum.',
             'high')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE lake_ri_documents DROP COLUMN IF EXISTS source_id")
    op.execute("ALTER TABLE lake_news DROP COLUMN IF EXISTS source_id")
    op.execute("""
        ALTER TABLE fundamentals
            DROP COLUMN IF EXISTS contributing_sources,
            DROP COLUMN IF EXISTS primary_source_id
    """)
    op.execute("ALTER TABLE stock_prices DROP COLUMN IF EXISTS source_id")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS metadata_source_id")
    op.execute("DROP INDEX IF EXISTS ix_data_sources_slug")
    op.execute("DROP TABLE IF EXISTS data_sources")
