# Production Legal Checklist

Targets any operator running this crawler against third-party sources for
commercial use. This is a checklist, not legal advice. The MIT license at
`./LICENSE` and the per-source notes in `./DISCLAIMER.md` are the primary
references; everything below operationalizes them.

## Before the first commercial user pays

- [ ] **`CRAWLER_CONTACT_EMAIL` set in env.** Every outbound HTTP request
  attaches an RFC 9110 `From:` header pointing here, so sources can find you
  without disabling your user-agent rotation. Defined in
  `crawler/services/config.py`; honored by `crawler/services/request_manager.py`.
- [ ] **Public Terms of Service and Privacy Policy** on your product site,
  referencing this crawler's role as your data engine and listing the public
  data sources you depend on (linkable from the rendaraq `/about/data-sources`
  page, which is generated from `GET /api/v1/sources`).
- [ ] **Takedown channel** — a dedicated email or form (e.g. `dmca@<your-domain>`)
  with a documented SLA. Mention it in your ToS, in `SECURITY.md`, and as the
  value of `CRAWLER_CONTACT_EMAIL`.
- [ ] **`data_sources` review** — open the seeded rows
  (`alembic/versions/d4e5f6a7b8c9_add_data_sources_registry.py`) and verify
  every `tos_url`, `risk_tier`, and `legal_basis` is accurate for your
  jurisdiction and product. Update via `UPDATE data_sources SET …`.
- [ ] **Source attribution visible** in your UI. Every record returned by the
  API embeds enough to render `via {display_name}` with a click-through to the
  upstream source. Don't strip it on the front end.
- [ ] **No mirrored content.** This codebase no longer mirrors CVM PDFs to a
  public CDN. If you bring back any mirror, document the legal basis and the
  removal SLA in your ToS first.
- [ ] **No full-text storage.** `LakeRIDocumentSchema` (public) omits
  `text_excerpt`; only `LakeRIDocumentInternalSchema` exposes it, and only
  for in-process consumers (LagoAI insight pipeline). If a future feature
  needs to surface text on the public API, get a parecer jurídico first.
- [ ] **Backfill ran.** Execute `uv run python scripts/backfill_data_sources.py`
  once after the `data_sources` migration so legacy rows are attributable in
  case of a takedown about historical data.

## Operating a takedown response (DMCA-style)

When a source publisher (e.g. InfoMoney) requests removal:

1. **Disable the source immediately** (no deploy required):
   ```sql
   UPDATE data_sources SET enabled = false WHERE slug = 'infomoney';
   ```
   Within ~30 seconds (registry cache TTL), the spider stops collecting from
   that slug and `GET /api/v1/sources` hides it from your transparency page.
2. **Identify affected rows**:
   ```sql
   SELECT id, url, published_at
   FROM lake_news
   WHERE source_id = (SELECT id FROM data_sources WHERE slug = 'infomoney')
   ORDER BY published_at DESC;
   ```
3. **Decide the response shape:**
   - *Soft hide* — UI filters out rows whose `source.enabled = false` (no
     data destruction; reversible if the source later renegotiates).
   - *Hard delete* — `DELETE FROM lake_news WHERE source_id = ...` (final).
   - *Selective delete* — only the specific URLs the complaint cites.
4. **Reply to the complainant** within your published SLA. Include:
   - Confirmation of action taken (hide / delete).
   - Affected row count.
   - Timestamp of the kill-switch flip.
5. **Audit trail** — record the incident in `data_sources.notes`:
   ```sql
   UPDATE data_sources
   SET notes = COALESCE(notes, '') || E'\n2026-MM-DD: takedown from <contact>, ref ...'
   WHERE slug = 'infomoney';
   ```
6. **Re-enable** (`enabled = true`) only after the dispute is resolved
   (renegotiation, ToS change, spider modification).

The `lake_ri_documents`, `stock_prices`, and `fundamentals.primary_source_id`
columns follow the same query pattern with their respective FK names.

## Source-specific notes

`DISCLAIMER.md` carries the per-source legal posture and risk tiers. Re-read
it before enabling a new source. Highlights:

- **CVM, BCB** (public-domain): low risk; attribution and disclaimers are
  enough.
- **RSS feeds** (rss-fair-use): store summary + URL + title only; never the
  full article body. Honor publisher takedown requests by disabling the slug
  and considering hard delete.
- **yfinance** (tos-restricted): the highest-risk tier still in the
  pipeline. Used only for prices (facts) and shares outstanding. Set
  `CRAWLER_CONTACT_EMAIL`, throttle aggressively in `request_manager.py` if
  asked, and be prepared to disable the slug on short notice.
- **Fundamentus and StatusInvest are no longer supported.** Their spiders
  were removed because their indicator databases are protected as
  compilations under Lei 9.610/98. The crawler now computes every indicator
  locally from raw CVM open data — see
  `crawler/services/financial_calculator.py`.

## Follow-up TODOs (not blocking launch)

These were intentionally deferred from the lineage rollout to keep the change
set small. Pick up before scaling user count significantly:

- **Wire `primary_source_id` and `contributing_sources` on `fundamentals`** —
  the enrichment chain (`crawler/engine/crawler_engine.py`) calls multiple
  spiders in sequence; the persistence point needs to record which slug last
  touched the row and which slugs contributed. Today these columns exist on
  the model but are populated only via the backfill script.
- **Wire `source_id` on `stock_prices`** — yfinance is the dominant source
  today; backfill covers historical rows, but new inserts also need the FK.
- **Per-field provenance on `fundamentals`** — beyond the snapshot-level
  attribution, store which source filled each field (`p_l_source`, etc.) if
  any source ever disputes a specific number.
- **Audit log table** — separate `data_source_audit_log` capturing every
  takedown action with operator, timestamp, affected rowcount, free text.
  Today the only audit trail is `data_sources.notes`, which is shared and
  unstructured.

## Not legal advice

This document is engineering-grade tooling for compliance posture. Decisions
that map directly to financial risk (litigation, fines, regulatory
disclosure) should be reviewed with a lawyer specialized in Brazilian
copyright law and online ToS enforcement before deployment.
