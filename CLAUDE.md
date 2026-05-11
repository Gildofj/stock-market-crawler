# CLAUDE.md - Stock Market Crawler

Project-specific instructions for Claude Code.

## 🏗️ Architecture & Core Principles
- **Pattern**: Crawler Engine (Spiders + Enrichment Chain) + FastAPI.
- **Data Flow**: Spiders → ETL → Services → PostgreSQL (SQLAlchemy + Alembic).
- **Standards**: Strict typing (Pydantic V2 / Type Hints), TDD, Clean Architecture.

## 🛠️ Commands
- **Install**: `uv sync`
- **Run Crawler**: `uv run python main.py`
- **Run API**: `uv run uvicorn api.main:app --reload`
- **Tests**: `uv run pytest` (Unit: `tests/unit`, Integration: `tests/integration`)
- **Migrations**: `uv run alembic revision --autogenerate -m "msg"` / `uv run alembic upgrade head`
- **Lint**: `uv run ruff check .`
- **Docker**: `docker-compose up` (PostgreSQL on 5433, Redis on 6379, Grafana on 3001)

## 🤖 Agent Routing

Adopt the agent from `.agents/agents/` based on the active file or task:

| File / Task | Agent | Skill |
|---|---|---|
| `crawler/spiders/`, `crawler/engine/`, `crawler/services/etl_service.py` | `crawler-specialist` | `new-spider`, `debug-spider` |
| `api/routers/`, `api/schemas.py`, `api/deps.py` | `api-architect` | `api-standard-endpoint` |
| `crawler/models/`, `alembic/` | `data-master` | `db-migration` |
| `tests/unit/`, `tests/integration/`, `conftest.py` | `test-guardian` | `write-tests` |
| `Dockerfile`, `docker-compose.yml`, `.github/workflows/` | `devops-engineer` | — |
| Feature end-to-end (multi-arquivo) | Start with `data-master`, then chain | `add-new-feature` |

## 🎨 Style Guidelines
- Absolute imports: `from crawler.services.data_service import DataService`.
- Self-documenting code. Mandatory type hints on all function signatures.
- No `print()` in production — use `loguru` logger.
- No `any` types — strict Pydantic V2 models.
