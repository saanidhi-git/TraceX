from datetime import datetime, timedelta, timezone


def demo_transactions() -> list[dict[str, object]]:
    start = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []

    def add(tx_id: str, source: str, destination: str, amount: float, minutes: int) -> None:
        rows.append({
            "transaction_id": tx_id,
            "source_account": source,
            "destination_account": destination,
            "amount": amount,
            "currency": "USD",
            "timestamp": (start + timedelta(minutes=minutes)).isoformat(),
            "channel": "bank_transfer",
            "status": "completed",
        })

    # Cycle and rapid pass-through.
    add("demo-001", "acct-a", "acct-b", 1200, 0)
    add("demo-002", "acct-b", "acct-c", 1180, 8)
    add("demo-003", "acct-c", "acct-a", 1150, 16)
    # Many-to-one collection with rapid onward transfers.
    add("demo-004", "acct-d", "acct-hub", 400, 25)
    add("demo-005", "acct-e", "acct-hub", 450, 30)
    add("demo-006", "acct-f", "acct-hub", 500, 35)
    add("demo-007", "acct-hub", "acct-relay", 1300, 40)
    add("demo-018", "acct-g", "acct-hub", 380, 38)
    add("demo-008", "acct-relay", "acct-out", 1250, 55)
    # Outgoing distribution and burst.
    for index, destination in enumerate(("acct-x", "acct-y", "acct-z"), start=9):
        add(f"demo-{index:03}", "acct-dist", destination, 350, index)
    # Benign control activity.
    add("demo-012", "acct-normal-1", "acct-normal-2", 42, 180)
    add("demo-013", "acct-normal-2", "acct-normal-3", 55, 720)
    # Branch and reconverge to exercise the cross-layer motif.
    add("demo-014", "acct-branch", "acct-branch-left", 700, 300)
    add("demo-015", "acct-branch", "acct-branch-right", 650, 302)
    add("demo-016", "acct-branch-left", "acct-merge", 680, 315)
    add("demo-017", "acct-branch-right", "acct-merge", 620, 318)
    return rows
