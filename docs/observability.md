# Observability Runbook

The crawler emits **structured JSON logs** (Google Cloud Logging) and
**OpenTelemetry traces** (exported to Cloud Trace in prod, to local Grafana
Tempo in dev). The stack stays inside the GCP free tier:

| Signal | Backend | Free-tier cap |
|---|---|---|
| Logs | Cloud Logging | 50 GiB / month |
| Traces | Cloud Trace | 2.5 M spans / month |
| Errors | Error Reporting | unlimited |

## Quick reference — env vars

| Var | Default | Prod | Effect |
|---|---|---|---|
| `LOG_FORMAT` | `human` | `gcp` | `human` colored stderr, `gcp` NDJSON stdout |
| `OTEL_ENABLED` | `false` | `false` (flip on demand) | Global kill switch |
| `OTEL_EXPORTER` | `console` | `gcp` | `console`, `otlp` (Tempo), `gcp` (Cloud Trace) |
| `OTEL_SAMPLE_RATIO` | `1.0` | `0.1` | `ParentBased(TraceIdRatioBased)` |
| `DEPLOYMENT_ENV` | `development` | `production` | OTel resource + log attribute |
| `SERVICE_VERSION` | `dev` | git SHA | OTel resource + log `serviceContext` |
| `GCP_PROJECT_ID` | from `GOOGLE_CLOUD_PROJECT` | — | Fully-qualifies the log↔trace link |

OTel SDK reads the standard ones directly: `OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`, `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`.

## Local dev

```bash
docker-compose up
curl -H "X-Request-Id: dev-001" http://localhost:8000/api/v1/companies
```

* **Logs**: terminal (colored) + Grafana → Explore → Loki, filter
  `{container="stock_market_crawler_api"}`.
* **Traces**: Grafana → Explore → Tempo, search by `Service Name = api` or
  paste the request id (`dev-001`) into "TraceQL".
* **Log → trace jump**: in any Loki log line, click the `trace_id` field;
  Grafana opens the matching Tempo trace via the `tracesToLogsV2` link
  provisioned in [grafana/provisioning/datasources/datasource.yaml](../grafana/provisioning/datasources/datasource.yaml).

## Enabling tracing in production (incremental)

Deploys ship with `OTEL_ENABLED=false`. Roll it on one workload at a time so
quota usage is observable.

1. **API first.** In Cloud Run console → service → "Edit & deploy new
   revision" → Variables tab, set `OTEL_ENABLED=true`, keep
   `OTEL_SAMPLE_RATIO=0.05` for the first hour. Deploy.
2. **Verify within 15 min.** Cloud Trace → "Trace list" → filter
   `service.name = api`. Confirm spans show resource attrs
   `deployment.environment=production` and `service.version=<sha>`.
3. **Bump sampling.** If span volume looks healthy (< 80k spans/hour leaves
   ample headroom under 2.5M/month), bump to `0.1`.
4. **Worker.** Same flip on the Cloud Run worker:
   `gcloud run services update stock-market-worker --update-env-vars=OTEL_ENABLED=true,OTEL_SAMPLE_RATIO=0.05`
   The new revision rolls automatically.
5. **RI Cloud Run Job.** Edit env at the job level; flush is handled by
   `shutdown_tracing()` in [crawler/tasks/lake_ri.py](../crawler/tasks/lake_ri.py)
   so traces survive the SIGTERM at completion.

## Jumping log → trace

Every JSON log line in production carries:

```json
"logging.googleapis.com/trace": "projects/<project>/traces/<32-hex>",
"logging.googleapis.com/spanId": "<16-hex>"
```

In Cloud Logging:
* Click any log entry; the right panel shows a "View trace" link to the
  matching Cloud Trace waterfall.
* Or, in the Logs Explorer query bar:
  `jsonPayload."logging.googleapis.com/trace"="projects/.../traces/<id>"`
  to retrieve every log line emitted during that trace.

In Cloud Trace, the inverse works too: open a trace → "Logs" tab on the
right panel surfaces correlated log entries.

## Log-based metrics (free alternative to custom metrics)

Custom OTel metrics burn the 150 MiB/month cap fast. For counters and
distributions, prefer **log-based metrics** — they read existing logs and
publish to Cloud Monitoring at no extra cost up to the 50 GiB ingest cap.

Example: count failed RI document parses per company.

1. Cloud Logging → "Logs-based Metrics" → "Create Metric".
2. Filter:
   ```
   resource.type="cloud_run_revision"
   jsonPayload.serviceContext.service="stock-market-crawler"
   severity=ERROR
   jsonPayload.message=~"RI.*failed"
   ```
3. Metric type: **Counter**; Label: `jsonPayload.extra.ticker`.
4. View in Cloud Monitoring → Metrics Explorer.

## Emergency kill switches

| Symptom | Action |
|---|---|
| Cloud Trace approaching quota | Set `OTEL_SAMPLE_RATIO=0.01` on the noisiest service, deploy. |
| Cloud Logging approaching 50 GiB | Set `LOG_LEVEL=WARNING` on the noisiest service; audit `logger.debug` calls. |
| Boot failure after OTel toggle | `OTEL_ENABLED=false` and re-deploy. The SDK's failure modes are guarded so this should not happen, but the switch is there. |
| Tempo container OOM in dev | Drop `block_retention` in [grafana/tempo/tempo.yaml](../grafana/tempo/tempo.yaml) or `docker volume rm stock-market-crawler_tempo_data`. |

## Troubleshooting

**No traces appearing in Tempo (dev):**
* Confirm the api/worker containers are on the same docker network as
  `tempo` — `docker compose ps` should show all on `stock-market-crawler_default`.
* `OTEL_EXPORTER_OTLP_ENDPOINT` must point to `http://tempo:4317` (compose
  service name, not `localhost`).
* The `BatchSpanProcessor` buffers up to 2s; hit the endpoint a couple of
  times before looking.

**`trace_id` missing from logs (prod):**
* `OTEL_ENABLED=false` means the OTel patcher in `core.logging` is a no-op
  for trace fields — `request_id` still appears via
  `CorrelationMiddleware`. To get `trace_id` in logs, enable tracing.

**Spans for `/health` flooding Cloud Trace:**
* `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` in the deploy.yml api job already
  excludes `/health,/docs,/redoc,/openapi.json,/`. Add more entries to that
  comma-separated list and re-deploy.
