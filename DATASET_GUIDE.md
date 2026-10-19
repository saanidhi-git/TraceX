# Dataset guide

## Bundled dataset and public demo

The app seeds a small, explicitly synthetic example into SQLite on first startup. It contains constructed cycle, collection, rapid pass-through, relay, distribution, and normal-control transactions. It contains no real people, businesses, or customer records. The example CSV is at `backend/data/demo_transactions.csv`; the seeded API demo is defined in `backend/app/demo.py`.

No IBM AMLSim, Elliptic, or PaySim dataset is downloaded or bundled, so this repository does **not** claim an external dataset version, selected upstream files, or external-data license compliance.

## Candidate datasets for a controlled evaluation

- **IBM AMLSim (preferred next dataset):** upstream project and dataset instructions: <https://github.com/IBM/AMLSim>. AMLSim generates configurable synthetic transaction networks with laundering typologies and labels. Select and record an explicit upstream release/commit, generated scenario files, parameters, and the license terms accompanying those files before use. This repository has not downloaded or benchmarked a particular release.
- **Elliptic Bitcoin transaction dataset:** upstream dataset page: <https://www.kaggle.com/datasets/ellipticco/elliptic-data-set>. It is a Bitcoin transaction graph with dataset-specific labels/features, significant class imbalance, and transaction entities rather than ordinary bank accounts. Confirm access and terms on the source before use; adapt its schema explicitly instead of treating it as interchangeable with bank transfers.
- **PaySim:** upstream research/simulator information: <https://github.com/EdgarLopezPhD/PaySim>. It is useful for transaction-level fraud baselines; it is not a complete real-world AML graph/network dataset. Confirm the specific file version and license in the source package.

Never infer the real-world guilt of an identifiable person or company from public labels or graph structure. Record dataset date, source URL/release, license, transform steps, schema mapping, limitations, and train/test separation in any research report.

## Upload contract

Accepted extensions: `.csv`, `.json`. CSV headers and JSON object keys are case-insensitive.

Required normalized fields:

| Canonical field | Accepted aliases | Validation |
|---|---|---|
| `transaction_id` | `transaction_id`, `transactionid`, `tx_id`, `id` | Unique per dataset; generated from row number if absent |
| `source_account` | `source_account`, `source`, `src`, `nameOrig`, `account_from` | Non-empty |
| `destination_account` | `destination_account`, `destination`, `dest`, `nameDest`, `account_to` | Non-empty |
| `amount` | `amount`, `transaction_amount`, `amt` | Finite positive number |
| `timestamp` | `timestamp`, `datetime`, `time`, `step` | ISO-8601 date/time; naive values interpreted as UTC |
| `currency` | `currency` | Optional, defaults to USD; three characters |
| `channel` | `channel`, `payment_channel`, `type` | Optional |
| `status` | `status`, `transaction_status` | Optional, defaults to completed |

JSON may be an array of transaction objects or an object with a `transactions` array. Invalid rows are rejected with row number, error, and submitted row. The upload response contains a bounded preview of errors; the complete error report is persisted and downloadable as JSON from `/api/v1/datasets/{dataset_id}/rejections.json`. Accepted rows remain available for analysis. Upload size defaults to 10 MiB and valid rows are capped at 50,000. Timestamps are normalized to UTC and duplicate IDs are rejected.

## Repeatable ingestion

Start the backend, then upload a CSV/JSON through the workspace or run:

```powershell
python backend\scripts\upload_dataset.py path\to\transactions.csv
```

The script reports the server's dataset ID and validation summary. No downloader silently substitutes generated data for a missing public dataset.
