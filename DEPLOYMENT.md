# Deployment

## Local container deployment

Copy `.env.example` to `.env`, review the upload and CORS settings, then:

```bash
docker compose up --build
```

Frontend: `http://localhost:8080`; API: `http://localhost:8000/api/v1/health`. Docker Compose stores SQLite under the named `graphsentinel-data` volume. Back up that volume before updating or removing the stack.

## Hosted deployment

The frontend can be built and hosted as static files on a static web host. Set `VITE_API_BASE_URL` to the public API origin plus `/api/v1` **at build time**, then run `npm run build` and publish `frontend/dist`.

The FastAPI backend can run on a container host. Configure:

- `GRAPHSENTINEL_DATA_DIR` on a persistent disk.
- `GRAPHSENTINEL_DATABASE` if the SQLite file should be at a particular mounted path.
- `GRAPHSENTINEL_CORS_ORIGINS` to only the exact frontend origins.
- `GRAPHSENTINEL_MAX_UPLOAD_BYTES` and `GRAPHSENTINEL_MAX_TRANSACTIONS` to fit available memory/runtime.
- An HTTPS reverse proxy and backup/retention policy.

The health probe is `GET /api/v1/health`. After deployment, verify health, load the demo dataset, launch a run, poll it to completion, inspect the graph, and download the JSON export.

## Production gaps to close

This repository is intentionally a single-instance demonstration. It has no user authentication, role checks, tenant isolation, CSRF strategy, audit/event trail, or multi-worker job coordination. Its fixed-window rate limiter is in-memory and per-process. Do not expose unauthenticated uploads to a public service with private data. Before public/prod deployment add authenticated authorization, per-tenant dataset access, quotas, durable asynchronous jobs, database migrations/backups, encryption and retention controls, security headers, monitoring, and a deployment-specific security review. Consider PostgreSQL once multi-instance/operational requirements exceed SQLite.

