# Architecture

## Data flow

1. React uploads CSV/JSON or selects the bundled synthetic dataset.
2. FastAPI validates file extension, byte limit, row schemas, timestamps and duplicate transaction IDs. Invalid rows are reported; valid rows and provenance are persisted to SQLite.
3. An analysis request is recorded and executed as a FastAPI background task. The graph service constructs a `networkx.MultiDiGraph` in the detector pipeline so parallel transaction events are retained.
4. Bounded rule detectors produce evidence-bearing findings. Scoring aggregates one strongest contribution per pattern category per account; ring grouping uses connected overlap among flagged accounts. An unsupervised, fixed-seed IsolationForest also computes per-analysis relative account anomaly ranks, separate from heuristic rules.
5. Results persist as a report record and are fetched by typed frontend services. JSON report output is validated against the versioned JSON Schema.

## Modules

- `backend/app/ingestion.py`: CSV/JSON parsing, alias mapping, row validation and duplicate detection.
- `backend/app/detectors.py`: bounded cycles and paths, smurfing, mule-structure indicators, heuristic scoring, and suspected-ring grouping.
- `backend/app/storage.py`: SQLite schema and repository functions for datasets and completed analysis.
- `backend/app/main.py`: FastAPI routes, input limits, CORS, in-memory request rate limiting, background job wiring, and strict report validation.
- `frontend/src/api.ts`: typed API boundary and centralized errors.
- `frontend/src/App.tsx`, `GraphView.tsx`: responsive workspace, analysis polling, and Cytoscape directed graph.

## Persistence and extension

SQLite is suitable for this local single-instance app. The current request rate limiter and background processing are process-local; horizontal scaling requires shared state and a durable job queue. The detector functions consume normalized transaction dictionaries and keep graph construction behind an internal NetworkX layer so a streaming or graph-database engine can replace it without changing API report semantics.

Uploaded transactions and analysis reports are stored in SQLite. There is no automatic deletion or tenant-level access control in this demo. Restrict access, configure persistent storage and retention, and add authorization before handling non-public datasets.
