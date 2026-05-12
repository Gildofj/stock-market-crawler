<!--
Thanks for contributing!

Make sure you've read CONTRIBUTING.md and that your commits follow Conventional Commits.
Security vulnerabilities must go through SECURITY.md — never a public PR.
-->

## Summary

<!-- 1-3 bullets: what changed and why. -->

-
-

## Type of change

<!-- Check all that apply. Aligns with Conventional Commits. -->

- [ ] `feat` — new user-facing feature
- [ ] `fix` — bug fix
- [ ] `perf` — performance improvement
- [ ] `refactor` — internal restructuring, no behavior change
- [ ] `docs` — documentation only
- [ ] `test` — adding or updating tests
- [ ] `build` — `pyproject.toml`, `Dockerfile`, `uv.lock`, etc.
- [ ] `ci` — GitHub Actions / workflows
- [ ] `chore` — repository maintenance
- [ ] **Breaking change** (also describe the migration path below)

## Related issues

<!-- e.g. Closes #123, Refs #456 -->

## Testing

<!-- How did you verify this works? What commands did you run? Did you add new tests? -->

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest` passes (unit + integration where relevant)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Documentation updated where applicable (`README.md`, `docs/`, env vars, Makefile targets)
- [ ] No secrets, real `DATABASE_URL`s, production domains, tokens, or personal data in code, tests, or fixtures
- [ ] No `print()` calls — uses `loguru` logger
- [ ] Strict typing on all new/changed signatures; no `Any` at module boundaries
- [ ] Absolute imports only; no inline imports
- [ ] **If adding a new spider / data source**: I have confirmed the target site permits programmatic access for educational/research use, and the spider uses `RequestManager` (not direct `requests`/`httpx`)
- [ ] Considered the impact on the daily 10-chunk GitHub Actions matrix (memory, Supabase pooler connections, runtime)

## Breaking change notes

<!-- If this is a breaking change, describe what consumers must do to migrate. Otherwise delete this section. -->
