import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DATABASE_PATH


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                transactions_json TEXT NOT NULL, created_at TEXT NOT NULL,
                warnings_json TEXT NOT NULL, rejected_rows_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(id),
                status TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS pattern_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL REFERENCES analyses(id),
                pattern_id TEXT NOT NULL,
                feedback TEXT NOT NULL CHECK (feedback IN ('false_positive', 'reviewed')),
                created_at TEXT NOT NULL
            );
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(datasets)")}
        if "rejected_rows_json" not in columns:
            db.execute("ALTER TABLE datasets ADD COLUMN rejected_rows_json TEXT NOT NULL DEFAULT '[]'")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_dataset(
    dataset_id: str,
    name: str,
    source: str,
    transactions: list[dict[str, Any]],
    warnings: list[str],
    rejected_rows: list[dict[str, Any]] | None = None,
) -> None:
    with connect() as db:
        db.execute(
            """INSERT INTO datasets
            (id, name, source, transactions_json, created_at, warnings_json, rejected_rows_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, name, source, json.dumps(transactions), now_iso(), json.dumps(warnings),
             json.dumps(rejected_rows or [])),
        )


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if row is None:
        return None
    transactions = json.loads(row["transactions_json"])
    accounts = {
        account
        for transaction in transactions
        for account in (transaction["source_account"], transaction["destination_account"])
    }
    return {
        "dataset_id": row["id"],
        "name": row["name"],
        "source": row["source"],
        "transaction_count": len(transactions),
        "account_count": len(accounts),
        "created_at": row["created_at"],
        "warnings": json.loads(row["warnings_json"]),
        "rejected_count": len(json.loads(row["rejected_rows_json"])),
        "rejected_rows": json.loads(row["rejected_rows_json"]),
        "transactions": transactions,
    }


def list_datasets() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT id, name, source, transactions_json, created_at, warnings_json, rejected_rows_json FROM datasets ORDER BY created_at DESC"
        ).fetchall()
    datasets = []
    for row in rows:
        transactions = json.loads(row["transactions_json"])
        accounts = {
            account for transaction in transactions
            for account in (transaction["source_account"], transaction["destination_account"])
        }
        datasets.append({
            "dataset_id": row["id"], "name": row["name"], "source": row["source"],
            "transaction_count": len(transactions), "account_count": len(accounts),
            "created_at": row["created_at"], "warnings": json.loads(row["warnings_json"]),
            "rejected_count": len(json.loads(row["rejected_rows_json"])),
        })
    return datasets


def save_analysis(analysis_id: str, dataset_id: str) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO analyses (id, dataset_id, status, created_at) VALUES (?, ?, 'running', ?)",
            (analysis_id, dataset_id, now_iso()),
        )


def finish_analysis(analysis_id: str, result: dict[str, Any]) -> None:
    with connect() as db:
        db.execute(
            "UPDATE analyses SET status = 'completed', result_json = ? WHERE id = ?",
            (json.dumps(result), analysis_id),
        )


def fail_analysis(analysis_id: str, error: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE analyses SET status = 'failed', error = ? WHERE id = ?",
            (error, analysis_id),
        )


def get_analysis(analysis_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if row is None:
        return None
    return {
        "analysis_id": row["id"],
        "dataset_id": row["dataset_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"],
    }


def list_analyses(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT a.id, a.dataset_id, a.status, a.created_at, a.result_json, a.error, d.name AS dataset_name
            FROM analyses a JOIN datasets d ON d.id = a.dataset_id
            ORDER BY a.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    history = []
    for row in rows:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        history.append({
            "analysis_id": row["id"], "dataset_id": row["dataset_id"], "dataset_name": row["dataset_name"],
            "status": row["status"], "created_at": row["created_at"],
            "summary": result["summary"] if result else None, "error": row["error"],
        })
    return history


def save_feedback(analysis_id: str, pattern_id: str, feedback: str) -> dict[str, Any]:
    created_at = now_iso()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO pattern_feedback (analysis_id, pattern_id, feedback, created_at) VALUES (?, ?, ?, ?)",
            (analysis_id, pattern_id, feedback, created_at),
        )
        return {"id": cursor.lastrowid, "analysis_id": analysis_id, "pattern_id": pattern_id,
                "feedback": feedback, "created_at": created_at}


def list_feedback(analysis_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT id, analysis_id, pattern_id, feedback, created_at FROM pattern_feedback WHERE analysis_id = ? ORDER BY id",
            (analysis_id,),
        ).fetchall()
    return [dict(row) for row in rows]
