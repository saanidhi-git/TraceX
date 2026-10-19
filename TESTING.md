# Testing and benchmarking

## Backend

From `backend` with dependencies installed:

```powershell
python -m pytest
```

The unit suite checks ingestion/duplicate rejection, baseline structural detector behavior, deterministic rule scores and model ranks, and a normal-network control. Start the app and check `GET /api/v1/health` for a deployment smoke test.

## Frontend

From `frontend`:

```powershell
npm install
npm test
npm run build
```

## Repeatable benchmark

From `backend`:

```powershell
python -m scripts.benchmark
```

The script prints CSV columns `transactions,analysis_seconds,python_peak_allocated_mib,patterns`. It constructs deterministic synthetic rows at 100, 1,000, and 5,000 events and measures the complete analysis pipeline. Peak memory uses Python `tracemalloc` allocations, not total native-process RSS; record that limitation, host CPU/RAM/OS, Python version, and dependency versions with results. These values are not SLOs; establish acceptance targets only after measurement on the intended deployment.

### Measured local baseline

Single standalone run on 2026-10-18: Windows 11 Home build 26300, Intel Core i5-13450HX (16 logical processors), 15.6 GiB RAM, Python 3.14.0, NetworkX 3.7, scikit-learn 1.9.1.

| Transactions | Analysis runtime | Python allocated peak | Findings |
|---:|---:|---:|---:|
| 100 | 0.775 s | 0.8 MiB | 276 |
| 1,000 | 1.288 s | 1.8 MiB | 276 |
| 5,000 | 9.635 s | 3.1 MiB | 206 |

Provisional **idle same-host** acceptance targets for a repeated three-run median are ≤5 s at 100 events, ≤5 s at 1,000, and ≤15 s at 5,000. The table is one run, not a stable certification; earlier concurrent runs were substantially slower (up to 56.329 s at 5,000), so rerun without contention and use the target deployment hardware before asserting these targets are met. The Python allocation figure excludes native-library allocations and is not process RSS.

## Current test scope

The core detectors, upload parsing, API analysis/report round-trip, report validation, graph filtering, upload errors, and review-feedback persistence have automated test coverage. A manual local browser smoke test confirmed the dashboard loaded API-backed dataset counts, ran analysis, and rendered graph view. The project does not yet have automated browser-driven end-to-end tests, model evaluation, or external AMLSim/Elliptic/PaySim benchmark results. Do not claim those checks have passed.
