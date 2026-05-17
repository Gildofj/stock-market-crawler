# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

When opening a pull request, add your entry under the `[Unreleased]` section using the appropriate subsection (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`). On release, the maintainer will rename `[Unreleased]` to the new version and add the date.

---

## [Unreleased]

### Added

- **Clean-room fundamentals pipeline**: `crawler/services/financial_calculator.py` implements every universal indicator (P/L, P/VP, ROE, ROIC, EV/EBITDA, margins, debt ratios, Graham, Bazin, CAGR) as pure functions over a `RawFinancials` dataclass.
- **`CVMDatasetService`** downloads and caches CVM Dados Abertos ZIPs (DFP, ITR, CAD) under `$TMPDIR/cvm_cache` with a configurable TTL.
- **`CVMSpider`** maps tickers to `CD_CVM`, extracts raw line items from DFP statements using account-code + descriptive fallbacks, and feeds the calculator to derive every indicator locally.
- **`bootstrap-worker-vm.yml`** workflow (`workflow_dispatch`) — one-time, idempotent setup for the Celery worker VM: enables OS Login, installs `docker.io`, enables the daemon at boot, and sanity-checks `docker pull`.
- **`docs/DEPLOYMENT.md`** now documents the three-job structure of `deploy.yml`, the bootstrap workflow, required IAM roles, and how the worker container is kept in sync.

### Removed

- **`FundamentusSpider` and `StatusInvestSpider`** — proprietary fundamentals scrapers. Their per-row numbers were facts (no IP protection), but the curated indicator databases they ship are protected as compilations under Lei 9.610/98. Indicators are now computed locally from raw CVM open data.
- Logo and ticker-discovery fallbacks that scraped the proprietary aggregators. `LogoService` now resolves logos from each company's own website only; `TickerService` falls back to Brapi → B3 instruments CSV → CVM CAD → curated blue-chip list.
- `data_sources` rows for `fundamentus` and `statusinvest` (migration `e5f6a7b8c9d0`), replaced by a new `b3` row covering the public B3 arquivos endpoint.

### Changed

- **`deploy.yml › deploy-worker`** now rolls the worker via `gcloud compute ssh` + `docker pull` / `docker run` instead of `gcloud compute instances update-container`. Secrets (`DATABASE_URL`, `REDIS_URL`) are base64-encoded through the SSH command line and written into `/etc/celery-worker.env` (mode 600) for `--env-file`. Artifact Registry auth on the VM uses a short-lived `gcloud auth print-access-token`.

### Fixed

- **Worker deploy failed** with `Instance doesn't have gce-container-declaration metadata key — it is not a container.` The worker VM is a plain Debian host, not a Container-Optimized OS container-VM, so `update-container` never applied; the GCP container-startup-agent path is also deprecated.
- Typo in the worker-verify step (`compute ssh` → `gcloud compute ssh`) that would have failed the job had it been reached.

### Security

- _Nothing yet._

---

## [0.1.0] — 2026-05-12

Initial public-quality release. The crawler engine, FastAPI surface, enrichment chain, and daily GitHub Actions matrix are all functional. Community Health Files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, issue/PR templates) are introduced in this release.

### Added

- **Community Health Files**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 + Ethical Use section), `SECURITY.md`, this `CHANGELOG.md`, and GitHub issue/PR templates under `.github/`.
- **Reliability scoring**: `ReliabilityService` computes a composite reliability score and grade per company; exposed via dedicated router.
- **Enrichment chain**: B3/yfinance → Fundamentus → StatusInvest with `CrawlResult` contract preserving partial results across sources. *(The Fundamentus/StatusInvest stages were removed in the next unreleased iteration — see the `[Unreleased]` section above.)*
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
