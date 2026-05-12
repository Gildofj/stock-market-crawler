# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

When opening a pull request, add your entry under the `[Unreleased]` section using the appropriate subsection (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`). On release, the maintainer will rename `[Unreleased]` to the new version and add the date.

---

## [Unreleased]

### Added

- _Nothing yet._

### Changed

- _Nothing yet._

### Fixed

- _Nothing yet._

### Security

- _Nothing yet._

---

## [0.1.0] — 2026-05-12

Initial public-quality release. The crawler engine, FastAPI surface, enrichment chain, and daily GitHub Actions matrix are all functional. Community Health Files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, issue/PR templates) are introduced in this release.

### Added

- **Community Health Files**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 + Ethical Use section), `SECURITY.md`, this `CHANGELOG.md`, and GitHub issue/PR templates under `.github/`.
- **Reliability scoring**: `ReliabilityService` computes a composite reliability score and grade per company; exposed via dedicated router.
- **Enrichment chain**: B3/yfinance → Fundamentus → StatusInvest with `CrawlResult` contract preserving partial results across sources.
- **Tiered HTTP client**: `curl_cffi` (Tier 1) with rotating User-Agents and exponential backoff; `nodriver` headless browser (Tier 2) as fallback for JS-heavy pages.
- **Sharded crawl entrypoint**: `main.py --chunk N --total-chunks 10` for parallel execution across a GitHub Actions matrix.
- **Observability stack**: Loguru → Promtail → Loki → Grafana provisioning under `grafana/`.
- **API**: FastAPI routers for companies, fundamentals, prices, and reliability with Redis-backed caching (`fastapi-cache2`) and rate limiting (`fastapi-limiter`).

### Changed

- **Architecture**: refactored to Clean Architecture layout — `api/` (presentation), `crawler/services/` (application), `crawler/models/` (domain), spiders + HTTP client (infrastructure).
- **Imports**: moved inline imports to the top of files and removed dead code paths (`3f1e206`).
- **Lint & types**: codebase passes `ruff check` and `pyright` strict (`039dfe1`).

### Performance

- **Parallel enrichment**: tickers within a sub-batch are now enriched concurrently via `asyncio.gather` with `Semaphore(15)`, replacing the previous sequential bottleneck (`a7c9f30`).
- **Bulk lookups**: `data_service.get_existing_symbols(...)` performs a single bulk query per sub-batch instead of per-ticker round-trips.

### Fixed

- **Supabase free-tier compatibility**: tuned in-process pool (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=3`) and switched to the transaction-mode pooler (port 6543) so that 10 parallel GHA chunks stay within the project-wide connection cap (`cdef906`).

### Security

- **Sanitized public config**: CORS allowlist moved out of source code into the `ALLOWED_ORIGINS` environment variable; production deployments now require an explicit allowlist via `ENV=production` (`51de321`).
- **Cloudflare-aware middleware**: production traffic must originate from Cloudflare IPs and carry `cf-connecting-ip`; bypass list restricted to documented public endpoints.
- **Secrets via env only**: all credentials (`DATABASE_URL`, `REDIS_URL`) loaded through `pydantic-settings`; `.env` is gitignored and `.env.example` ships without real values.

### Documentation

- Initial `README.md` with feature list, getting-started, project structure.
- `docs/ARCHITECTURE.md` — enrichment chain, data flow diagram, tiered HTTP client, reliability scoring.
- `docs/DEPLOYMENT.md` — Render + Supabase (transaction pooler) + GitHub Actions matrix.
- `LICENSE` includes a **LEGAL DISCLAIMER & EDUCATIONAL NOTICE** clarifying ToS-compliance responsibility and educational-purpose intent.

---

[Unreleased]: https://github.com/gildofj/stock-market-crawler/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gildofj/stock-market-crawler/releases/tag/v0.1.0
