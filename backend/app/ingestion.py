import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.schemas import Transaction


ALIASES = {
    "transaction_id": ("transaction_id", "transactionid", "tx_id", "id"),
    "source_account": ("source_account", "source", "src", "nameorig", "account_from"),
    "destination_account": ("destination_account", "destination", "dest", "namedest", "account_to"),
    "amount": ("amount", "transaction_amount", "amt"),
    "currency": ("currency",),
    "timestamp": ("timestamp", "datetime", "time", "step"),
    "channel": ("channel", "payment_channel", "type"),
    "status": ("status", "transaction_status"),
}


def _normalize_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("each transaction row must be an object")
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    mapped: dict[str, Any] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized and normalized[alias] not in (None, ""):
                mapped[target] = normalized[alias]
                break
    if "timestamp" in mapped:
        raw_timestamp = mapped["timestamp"]
        try:
            parsed = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            mapped["timestamp"] = parsed.astimezone(timezone.utc)
        except ValueError as exc:
            raise ValueError("timestamp must be an ISO-8601 datetime") from exc
    mapped.setdefault("transaction_id", f"row-{index}")
    mapped.setdefault("currency", "USD")
    return mapped


def parse_upload(content: bytes, filename: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "csv":
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
    elif suffix == "json":
        value = json.loads(content)
        rows = value if isinstance(value, list) else value.get("transactions") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise ValueError("JSON must be an array of transactions or an object with a transactions array")
    else:
        raise ValueError("Only .csv and .json uploads are supported")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2 if suffix == "csv" else 1):
        try:
            normalized = _normalize_row(row, index)
            transaction = Transaction.model_validate(normalized)
            if transaction.transaction_id in seen_ids:
                raise ValueError(f"duplicate transaction_id: {transaction.transaction_id}")
            seen_ids.add(transaction.transaction_id)
            accepted.append(transaction.model_dump(mode="json"))
        except (ValidationError, ValueError, TypeError) as exc:
            rejected.append({"row": index, "error": str(exc), "data": row})
    warnings = [f"{len(rejected)} invalid row(s) were rejected"] if rejected else []
    return accepted, rejected, warnings
