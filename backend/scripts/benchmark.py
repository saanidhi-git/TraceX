import tracemalloc
import time
from datetime import datetime, timedelta, timezone

from app.detectors import analyze


def synthetic_transactions(size: int) -> list[dict[str, object]]:
    origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "transaction_id": f"bench-{index}",
            "source_account": f"account-{index % 1000}",
            "destination_account": f"account-{(index + 1) % 1000}",
            "amount": float(index % 500 + 1),
            "currency": "USD",
            "timestamp": (origin + timedelta(seconds=index)).isoformat(),
        }
        for index in range(size)
    ]


if __name__ == "__main__":
    for size in (100, 1_000, 5_000):
        txs = synthetic_transactions(size)
        dataset = {
            "dataset_id": f"bench-{size}", "name": f"synthetic-{size}", "source": "synthetic_benchmark",
            "transaction_count": size, "account_count": min(size, 1000),
            "created_at": datetime.now(timezone.utc).isoformat(), "warnings": [],
        }
        started = time.perf_counter()
        tracemalloc.start()
        report = analyze(txs, dataset, {})
        elapsed = time.perf_counter() - started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mib = peak_bytes / (1024 * 1024)
        print(f"{size},{elapsed:.3f},{peak_mib:.1f},{report['summary']['patterns_detected']}")
