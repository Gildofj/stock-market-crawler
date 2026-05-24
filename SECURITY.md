# Security Policy

Thanks for helping keep `stock-market-crawler` and its users safe. This document describes how to report a vulnerability, what is in and out of scope, and what hardening is already in place.

---

## Supported Versions

The project is pre-1.0. Only the `main` branch receives security patches.

| Version | Supported |
|---|---|
| `main` (latest commit) | :white_check_mark: |
| Older commits / tags | :x: |

Once the project reaches `1.0.0`, this table will be updated to reflect a longer-term support window for the latest minor.

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue, pull request, or discussion for security problems.**

Use one of the private channels below:

1. **Preferred — GitHub Security Advisories**
   Go to the repository's `Security` tab → **Report a vulnerability**. This opens a private advisory only visible to maintainers.

2. **Fallback — Email**
   Send a report to **security@gildofj.dev**. Include the same information requested below.

### What to include

- A description of the issue and the impact you believe it has.
- Reproduction steps — minimal, deterministic if possible.
- Affected commit hash or version.
- Logs, payloads, or proof-of-concept (strip secrets before sharing).
- Your preferred attribution for the eventual fix (handle, name, anonymous).

### Response targets

| Severity | First response | Mitigation / patch |
|---|---|---|
| Critical (RCE, credential leak, privilege escalation) | 72 hours | 14 days |
| High (auth bypass, data exposure) | 5 business days | 30 days |
| Medium / Low | 10 business days | next minor release |

You will receive an acknowledgement, a tracking advisory, and a coordinated disclosure date. Public disclosure happens **after** a fix is merged and released.

---

## Scope

The following are **in scope** for security reports:

- **API (`api/`)**: authentication/authorization gaps, SSRF, request smuggling, cache poisoning, CORS misconfiguration, deserialization issues, rate-limit bypass.
- **Crawler (`crawler/`)**: command injection or path traversal in ETL/data services, unsafe deserialization, log injection, SQL injection in ORM usage.
- **Database & migrations (`alembic/`)**: privilege escalation, destructive migration patterns, secrets in migration files.
- **Configuration**: secrets accidentally committed, insecure defaults in `.env.example`, weak CORS/CSRF defaults.
- **Dependency vulnerabilities**: known CVEs in pinned dependencies (`pyproject.toml`, `uv.lock`).
- **CI/CD (`.github/workflows/`)**: workflow injection, secret exposure, untrusted-input execution.

The following are **out of scope**:

- **Anti-bot behavior of the HTTP client** (`crawler/services/request_manager.py`). The use of `curl_cffi` (TLS fingerprinting) and `nodriver` (headless browser) is a documented **resilience strategy** for transient blocks — see `docs/ARCHITECTURE.md` → "Tiered HTTP Client". It is not considered a vulnerability of this project.
- **Third-party site behavior**: blocks, rate limits, ToS enforcement, or legal actions taken by data providers (B3, CVM Dados Abertos, Yahoo Finance) against operators of this software. Compliance with Terms of Service and `robots.txt` is the operator's responsibility — see [LEGAL DISCLAIMER in LICENSE](./LICENSE).
- **Denial-of-service against this repository itself** through automated tooling (Dependabot, CI minutes, etc.) when the underlying configuration is correct.
- **Issues requiring physical access** to a host already compromised, or requiring an attacker who is already a project maintainer.

---

## Current Hardening

This section is published as a transparency aid for auditors, downstream operators, and contributors. It reflects the state of the `main` branch.

### API surface

- **CORS**: production deployments require an explicit `ALLOWED_ORIGINS` allowlist (sanitised in commit `51de321`). Wildcard origins are not accepted when `ENV=production`.
- **Cloudflare middleware** (`api/security.py`): when `ENV=production`, requests must originate from Cloudflare IP ranges and carry `cf-connecting-ip`. Bypass paths are limited to `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`, `/favicon.ico`.
- **Rate limiting** (`api/limiter.py`): 10 requests per minute global default via `pyrate-limiter` with an in-process `InMemoryBucket`. Cloud Run min-instances stays at 0 and Cloudflare handles edge L7 protections.
- **Compression & transport**: `GZipMiddleware` enabled; TLS terminates at Cloudflare, then Cloud Run.
- **Response models**: all routers serialise through Pydantic v2 schemas in `api/schemas.py` — ORM objects are never returned directly.

### Secrets management

- Secrets are loaded exclusively from environment variables via `pydantic-settings` (`crawler/services/config.py`).
- `.env` is `.gitignore`d; only `.env.example` (no real values) ships in the repo.
- Production deployments inject `DATABASE_URL`, `API_KEY`, `ALLOWED_ORIGINS`, and `ENV` via Google Secret Manager (consumed by Cloud Run at startup); GitHub Actions reads them through `gcloud secrets versions access` only at deploy time.
- Supabase connections use the **transaction-mode pooler (port 6543)** — see `docs/DEPLOYMENT.md` — which reduces blast radius if a single client misbehaves.

### Data layer

- Database access goes exclusively through SQLAlchemy 2.0 with parameter binding. No string interpolation in queries.
- Alembic migrations are version-controlled and replayable; the legacy SQL bootstrap under `crawler/db/migrations/` is retained for reference only.
- A small connection pool (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=3` by default) limits per-process connection exhaustion when the 10-chunk GHA matrix runs in parallel.

### Supply chain

- Dependencies are pinned via `uv.lock`.
- We recommend enabling **Dependabot** alerts and security updates on forks/mirrors.
- New dependencies should be reviewed against `pyup`, `osv.dev`, or `safety` before merge.

---

## Legal & Ethical Note

This software is published for **educational and research purposes**, as stated in the [LICENSE](./LICENSE) (LEGAL DISCLAIMER & EDUCATIONAL NOTICE) and reaffirmed in the [CODE_OF_CONDUCT](./CODE_OF_CONDUCT.md) (Ethical Use section).

Two implications for security reports:

1. **The crawler does not automatically parse `robots.txt`.** Operators are responsible for verifying that their use of this software complies with each target site's Terms of Service and crawl directives. A report stating that "this project does not respect robots.txt" is a known design choice, not a vulnerability — it is delegated to the operator.
2. **Commercial use requires independent legal review.** If you intend to deploy this software in a commercial context, evaluate ToS compliance, data licensing, and applicable regulations (LGPD/GDPR, market data redistribution rules) before reporting "lack of compliance features" as a vulnerability.

Reports that fall under these two cases will be acknowledged and closed as `out-of-scope`. Genuine technical vulnerabilities — even when discovered while exercising scraping behavior — remain in scope and welcome.

---

## Data source takedown requests

If you are a content publisher (newsroom, regulator, market data provider) and
you have observed an instance of this crawler collecting or redistributing
your content and want it stopped or removed, contact the **operator** of the
deployment you observed — not the upstream repository maintainers.

A starting point: every request emitted by a properly-configured deployment
carries an RFC 9110 `From:` header (see `CRAWLER_CONTACT_EMAIL` in
`crawler/services/config.py`). That email is the operator's documented
takedown channel for that deployment.

For the **rendaraq** deployment specifically, takedown requests should go to
the channel listed on the rendaraq website (`/about/data-sources` or the
footer contact). Reports filed against the upstream repository will be
acknowledged but cannot remove data held by individual deployments.

Operators can disable a source instantly without a deploy via:

```sql
UPDATE data_sources SET enabled = false WHERE slug = '<slug>';
```

See `docs/PRODUCTION_LEGAL_CHECKLIST.md` for the full takedown workflow.

---

## Acknowledgements

Researchers who report valid vulnerabilities will be credited in the corresponding GitHub Security Advisory and in `CHANGELOG.md` under the `Security` section of the release, unless they request anonymity.

Thank you for contributing to the safety of this project. :shield:
