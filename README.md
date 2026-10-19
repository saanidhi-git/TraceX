# GraphSentinel

GraphSentinel is an end-to-end, graph-based transaction-risk demonstration. It ingests CSV/JSON transactions, preserves multi-edges in a directed NetworkX graph, runs bounded explainable structural detectors, ranks accounts with a transparent heuristic plus a separately reported unsupervised IsolationForest anomaly rank, groups overlapping flagged structures, and exports a schema-validated JSON report.

> **Investigative lead only.** A structural flag or heuristic score is not a calibrated probability, a finding of fact, or proof that an account or its owner committed a crime. The bundled dataset is synthetic.

## Run locally (Windows PowerShell)

Requirements: Python 3.11+ and Node.js 20.19+ (or 22.12+).

```powershell
Copy-Item .env.example .env
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The API is at <http://localhost:8000>, and interactive OpenAPI docs are at <http://localhost:8000/docs>. Python 3.11+ is supported; the backend Docker image uses Python 3.12.

### Linux / macOS

```bash
cp .env.example .env
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```bash
cd frontend && npm install && npm run dev
```

### Docker

```bash
docker compose up --build
```

Open <http://localhost:8080>. SQLite data persists in the `graphsentinel-data` volume.

## Use the application

1. Open **Datasets** and choose the bundled `GraphSentinel Synthetic Demonstration` dataset, or upload CSV/JSON.
2. Start analysis. The backend runs asynchronously and persists status/results in SQLite.
3. Use the overview, detection explorer, account risk, and transaction graph pages to inspect real API results.
4. Download the report from **Reports**. The API validates the report against [report.schema.json](backend/app/report.schema.json) before returning it.

To upload the included small sample using the helper:

```powershell
python backend\scripts\upload_dataset.py backend\data\demo_transactions.csv
```

CSV/JSON accepted fields and aliases are summarized in [DATASET_GUIDE.md](DATASET_GUIDE.md).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for service boundaries and persistence; [DETECTION_METHODOLOGY.md](DETECTION_METHODOLOGY.md) for the versioned rule thresholds and caveats; [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for routes and response shapes.

## Tests and measurements

```powershell
cd backend
python -m pytest
python -m scripts.benchmark
```

```powershell
cd frontend
npm test
npm run build
```

See [TESTING.md](TESTING.md). Benchmark results depend on the host; do not treat measurements from another machine as a performance guarantee.

## Configuration

Copy `.env.example` to `.env`. The backend reads:

| Variable | Default | Purpose |
|---|---:|---|
| `GRAPHSENTINEL_DATA_DIR` | `./data` | Dataset database directory |
| `GRAPHSENTINEL_DATABASE` | `<data dir>/graphsentinel.sqlite3` | SQLite database path |
| `GRAPHSENTINEL_MAX_UPLOAD_BYTES` | 10 MiB | In-memory upload size cap |
| `GRAPHSENTINEL_MAX_TRANSACTIONS` | 50,000 | Accepted rows per dataset and hard analysis ceiling |
| `GRAPHSENTINEL_CORS_ORIGINS` | localhost and 127.0.0.1 dev/demo origins | Exact browser origins |

The frontend `VITE_API_BASE_URL` is compiled into the Vite bundle. Rebuild the frontend after changing it.

## Limitations and deployment

This is a bounded, single-instance demonstration, not a regulated production AML product. The unsupervised model has no labeled training or held-out accuracy evaluation and is not a crime prediction. It has no analyst authentication or tenant isolation; do not expose it to the public Internet with sensitive data. Before production use, add identity/authorization, per-tenant data isolation, durable job queue, audit trail, encrypted storage, retention controls, operational monitoring, and a threat-reviewed deployment. Refer to [DEPLOYMENT.md](DEPLOYMENT.md).
