# API documentation

Base path: `/api/v1`. Interactive Swagger UI is exposed by FastAPI at `/docs`.

## Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health and version |
| `GET` | `/datasets` | Dataset metadata |
| `GET` | `/datasets/{dataset_id}` | Metadata and up to 100 preview rows |
| `POST` | `/datasets/upload` | Multipart CSV/JSON ingestion |
| `GET` | `/datasets/{dataset_id}/rejections.json` | Download the complete JSON row-error report for an uploaded dataset |
| `POST` | `/analysis/run` | Queue bounded analysis; returns HTTP 202 |
| `GET` | `/analysis/history` | Latest analysis runs with status and summary |
| `GET` | `/analysis/{analysis_id}` | Status, error, and completed summary |
| `GET` | `/analysis/{analysis_id}/patterns` | Paginated findings |
| `GET` | `/analysis/{analysis_id}/accounts` | Paginated account risk scores |
| `GET` | `/analysis/{analysis_id}/rings` | Paginated suspected groups |
| `GET` | `/analysis/{analysis_id}/feedback` | Read submitted analyst review markers |
| `POST` | `/analysis/{analysis_id}/feedback` | Persist a false-positive or reviewed marker for a finding |
| `GET` | `/analysis/{analysis_id}/graph` | Directed graph payload, capped at 1,000 transactions; supports `since`, `until`, `minimum_amount`, `account_id`, `pattern_type`, `risk_level`, and `ring_id` filters |
| `GET` | `/analysis/{analysis_id}/export/json` | Versioned, JSON-Schema-validated report |

List-style responses use `{ "items": [], "total": 0, "limit": 500, "offset": 0 }`; limit is clamped to 1–1,000. Graph returns `nodes`, `edges`, and `truncated`. Errors use a stable `error.code` and `error.message` shape for request validation, plus FastAPI's `detail` object for endpoint-specific errors. Rate limit response is HTTP 429.

## Run analysis

```json
{
  "dataset_id": "demo-graphsentinel",
  "config": {
    "min_cycle_length": 3,
    "max_cycle_length": 5,
    "smurf_min_counterparties": 3
  }
}
```

Response:

```json
{"analysis_id":"an-...","dataset_id":"demo-graphsentinel","status":"running"}
```

Poll the status endpoint, then fetch findings and report. Unknown configuration fields are ignored; supplied thresholds and resource caps are validated against backend bounds before queueing, and the resulting effective config is included in the export.

## Export schema

The report includes `schema_version`, `analysis_id`, `dataset`, `analysis_timestamp`, `summary`, `patterns`, `accounts`, `rings`, `model`, `detector_config`, and `warnings`. The exact required JSON Schema lives in `backend/app/report.schema.json` and is validated on every export. No third-party evaluator schema was supplied. The `model` object documents the per-analysis unsupervised IsolationForest, its training mode, features, score semantics, and caveat. Account rows expose `model_anomaly_score` separately from `risk_score`.
