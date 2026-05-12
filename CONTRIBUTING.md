# Contributing to Stock Market Crawler

First off, thanks for taking the time to contribute! :tada:

This document describes how to propose changes, the conventions we follow, and what to expect during review. It applies to bug reports, feature requests, and pull requests.

By participating in this project you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Workflow](#workflow)
- [Commit Convention](#commit-convention)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs & Requesting Features](#reporting-bugs--requesting-features)
- [Security Vulnerabilities](#security-vulnerabilities)

---

## Ways to Contribute

| Type | How |
|---|---|
| :bug: Bug reports | Open an [issue](../../issues/new/choose) using the **Bug report** template. |
| :sparkles: Feature requests | Open an [issue](../../issues/new/choose) using the **Feature request** template. |
| :book: Documentation | PRs to `README.md`, `docs/`, or inline docstrings are very welcome. |
| :spider: New spider | Add a data source under `crawler/spiders/`. See [Adding a New Spider](#adding-a-new-spider). |
| :test_tube: Tests | Increasing coverage on `crawler/`, `api/`, or services is always appreciated. |
| :hammer_and_wrench: Refactor / Performance | Open a draft PR first to align on the approach. |

---

## Development Setup

### Prerequisites

- **Python 3.12+**
- **Docker** & Docker Compose
- **uv** (package manager) — install with `make install-uv-user` or follow [astral.sh/uv](https://github.com/astral-sh/uv)

### Bootstrap

```bash
git clone https://github.com/<your-username>/stock-market-crawler.git
cd stock-market-crawler

# 1. Environment variables
cp .env.example .env

# 2. Install dependencies
uv sync

# 3. Start infrastructure (PostgreSQL, Redis, Grafana, Loki, Promtail)
docker-compose up -d

# 4. Apply migrations
uv run alembic upgrade head

# 5. Sanity check — run the test suite
uv run pytest
```

> :bulb: All workflows have shortcuts in the [`Makefile`](./Makefile). Run `make help` to see available targets.

### Common Tasks

```bash
# Run the crawler (full ticker set)
uv run python main.py

# Run a single shard (mimics one GHA chunk)
uv run python main.py --chunk 0 --total-chunks 10

# Run the API with hot reload
uv run uvicorn api.main:app --reload

# Lint + format
uv run ruff check .
uv run ruff format .

# Type-check
uv run pyright
```

---

## Project Structure

A condensed view of where things live:

```
api/         FastAPI application — routers, schemas, deps, security, limiter
crawler/     Core domain
  engine/    Enrichment chain orchestration + advanced metrics
  spiders/   Data sources (B3, Fundamentus, StatusInvest, Macro)
  services/  Business logic — request_manager, etl, data, reliability, ...
  models/    SQLAlchemy ORM + Pydantic schemas + CrawlResult contract
alembic/     Database migrations
tests/       unit/ + integration/
docs/        ARCHITECTURE.md, DEPLOYMENT.md
.github/     Workflows, issue/PR templates
```

A full tour lives in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

---

## Workflow

We follow a lightweight **GitHub Flow**:

1. **Fork** the repository (external contributors) or create a topic **branch** off `main` (maintainers).
2. Use a descriptive branch name: `feat/reliability-grade-cache`, `fix/statusinvest-timeout`, `docs/contributing-guide`.
3. Make small, focused commits — see [Commit Convention](#commit-convention).
4. **Rebase** on `main` before opening a PR — keep history linear.
5. Open a **Pull Request** against `main`. Fill out the PR template.
6. Address review feedback by pushing new commits (don't force-push during review; squash happens at merge time).

---

## Commit Convention

This project follows **[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)**. The commit message drives the [changelog](./CHANGELOG.md) and informs the next semver bump.

```
<type>(<optional-scope>): <short summary>

<optional body — what & why, not how>

<optional footer — BREAKING CHANGE: …, Refs #123>
```

### Allowed types

| Type | Use for |
|---|---|
| `feat` | A new user-facing feature |
| `fix` | A bug fix |
| `perf` | Performance improvement without behavior change |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `docs` | Documentation only |
| `test` | Adding/updating tests only |
| `build` | Build system, `pyproject.toml`, `Dockerfile`, `uv.lock` |
| `ci` | GitHub Actions workflows |
| `chore` | Repository maintenance with no production impact |

### Examples

```
feat(api): expose /reliability/{symbol}/history endpoint
fix(statusinvest): retry on 504 and skip ticker after 3 failures
perf(engine): parallelize ticker enrichment within a sub-batch
docs(deployment): clarify Supabase transaction pooler usage
```

### Breaking changes

Append `!` after the type/scope **and** include a `BREAKING CHANGE:` footer:

```
feat(api)!: rename /companies to /tickers

BREAKING CHANGE: /companies route was removed. Use /tickers.
```

---

## Code Standards

| Topic | Rule |
|---|---|
| **Style** | `ruff format` (line length 100, `py312` target). |
| **Lint** | `ruff check` must pass. Selected rules: `E, F, I, N, W, B, C4, UP`. |
| **Types** | Strict typing. All function signatures must have type hints. Pydantic V2 models, never `dict[str, Any]` at boundaries. `any` is a failure. |
| **Imports** | Absolute imports only (`from crawler.services.data_service import DataService`). Top-of-file — no inline imports. |
| **Logging** | `loguru` only. No `print()` in production code. |
| **i18n** | Never hardcode user-facing strings; use the established helpers. |
| **Comments** | Self-documenting code over comments. Only comment **why**, never **what**. |
| **Domain leakage** | Never expose ORM models from API responses — always wrap in Pydantic schemas under `api/schemas.py`. |

These rules are enforced by `ruff` and `pyright`. CI will fail PRs that violate them.

---

## Testing

We follow **Test-Driven Development** wherever practical.

| Suite | Location | Command |
|---|---|---|
| Unit | `tests/unit/` | `uv run pytest tests/unit -v` |
| Integration (DB) | `tests/integration/` | `uv run pytest tests/integration -v` |
| Full | `tests/` | `uv run pytest -v` |

### Guidelines

- New features **must** ship with tests. New spiders need at minimum unit tests covering parsing + fallback behavior.
- Bug fixes **must** ship with a regression test that fails on the previous code.
- Mock external HTTP at the `RequestManager` boundary — do not hit live B3/StatusInvest/Fundamentus in tests.
- Integration tests use the Docker Postgres on port `5433`. Bring it up with `docker-compose up -d db`.

### Adding a New Spider

> :warning: **Legal & ethical attestation.** Before proposing a new data source, confirm that the target site permits programmatic access for educational/research use, or that your use case is otherwise allowed under its Terms of Service. This project does **not** parse `robots.txt` automatically — compliance is the operator's responsibility per the [LEGAL DISCLAIMER in LICENSE](./LICENSE) and the [Ethical Use](./CODE_OF_CONDUCT.md#ethical-use-of-this-project) section of the Code of Conduct. PRs that bypass authentication, CAPTCHA, or paywalls will not be accepted.

1. Subclass `crawler.spiders.base_spider.BaseSpider`.
2. Return a `CrawlResult` (`crawler/models/contract.py`) — never raw dicts.
3. Use `RequestManager` for all HTTP. Don't import `requests` / `httpx` directly inside the spider.
4. Add the spider to the enrichment chain in `CrawlerEngine`.
5. Add unit tests under `tests/unit/spiders/`.

---

## Pull Request Process

1. **Open as draft** if you want early feedback or to validate the approach.
2. Make sure the following pass locally before requesting review:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pyright
   uv run pytest
   ```
3. Update `CHANGELOG.md` under the `[Unreleased]` section.
4. Update relevant documentation (`README.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, env vars).
5. Fill out the PR template completely — especially the **Why** and **Testing** sections.
6. Link related issues (`Closes #123`).
7. One approving review from a maintainer is required before merge. PRs are merged with **squash & merge** so a clean Conventional Commit subject lands on `main`.

### What we look for in review

- Correctness and test coverage.
- Adherence to Clean Architecture boundaries (no UI → domain leaks, no spider importing services that import spiders, etc.).
- No dead code, commented-out blocks, or speculative abstractions.
- Backwards compatibility unless a `BREAKING CHANGE` is explicitly justified.
- Performance impact on the daily 10-chunk matrix run.

---

## Reporting Bugs & Requesting Features

Use the issue templates — they ensure we have the context to act:

- :bug: [Bug report](../../issues/new?template=bug_report.yml)
- :sparkles: [Feature request](../../issues/new?template=feature_request.yml)

When reporting a bug, please include:

- Repro steps (commands run, ticker/symbol involved, chunk index if applicable).
- Logs (with `LOG_LEVEL=DEBUG`) — strip secrets first.
- Environment: OS, Python version, `uv --version`, whether running locally or on Render/GHA.

---

## Security Vulnerabilities

**Do not open a public issue for security problems.** Follow the responsible-disclosure process in [`SECURITY.md`](./SECURITY.md).

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE) and that you have the right to submit them under that license.
