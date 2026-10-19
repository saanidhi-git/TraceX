import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from jsonschema import Draft202012Validator

from app.core.config import CORS_ORIGINS, MAX_TRANSACTIONS, MAX_UPLOAD_BYTES
from app.demo import demo_transactions
from app.detectors import analyze, validate_config
from app.ingestion import parse_upload
from app.schemas import AnalysisRequest, PatternFeedbackRequest
from app.storage import (
    fail_analysis, finish_analysis, get_analysis, get_dataset, initialize,
    list_analyses, list_datasets, list_feedback, save_analysis, save_dataset, save_feedback,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("graphsentinel")
@asynccontextmanager
async def lifespan(application: FastAPI):
    initialize()
    if not list_datasets():
        rows = demo_transactions()
        save_dataset(
            "demo-graphsentinel", "GraphSentinel Synthetic Demonstration", "synthetic", rows,
            ["Synthetic demonstration fixture; not real customer or financial data."],
        )
    yield


app = FastAPI(
    title="GraphSentinel API",
    version="1.0.0",
    description="Explainable graph-based transaction risk analysis.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)
request_log: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    if request.url.path.startswith("/api/") and request.url.path != "/api/v1/health":
        now = time.monotonic()
        address = request.client.host if request.client else "unknown"
        if len(request_log) > 10000:
            for client, stamps in list(request_log.items()):
                if not stamps or now - stamps[-1] >= 60:
                    request_log.pop(client, None)
        request_log[address] = [stamp for stamp in request_log[address] if now - stamp < 60]
        if len(request_log[address]) >= 60:
            return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Request limit exceeded"}})
        request_log[address].append(now)
    return await call_next(request)


def _run_analysis(analysis_id: str, dataset_id: str, config: dict[str, Any]) -> None:
    try:
        dataset = get_dataset(dataset_id)
        if dataset is None:
            raise ValueError("Dataset not found")
        started_at = time.perf_counter()
        result = analyze(dataset["transactions"], dataset, config)
        result["summary"]["analysis_runtime_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        result["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()
        finish_analysis(analysis_id, result)
    except Exception as exc:
        logger.exception("Analysis %s failed", analysis_id)
        fail_analysis(analysis_id, "Analysis could not be completed. Check server logs for details.")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "graphsentinel-api", "version": app.version}


@app.get("/api/v1/datasets")
def datasets() -> list[dict[str, Any]]:
    return [{key: value for key, value in dataset.items() if key != "transactions"} for dataset in list_datasets()]


@app.get("/api/v1/datasets/{dataset_id}")
def dataset_detail(dataset_id: str) -> dict[str, Any]:
    dataset = get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(404, detail={"code": "dataset_not_found", "message": "Dataset not found"})
    preview = dataset["transactions"][:100]
    return {**{key: value for key, value in dataset.items() if key not in {"transactions", "rejected_rows"}},
            "preview": preview, "preview_truncated": dataset["transaction_count"] > len(preview)}


@app.post("/api/v1/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "").name
    if not filename.lower().endswith((".csv", ".json")):
        raise HTTPException(415, detail={"code": "unsupported_file", "message": "Upload a CSV or JSON file"})
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail={"code": "upload_too_large", "message": f"Maximum upload size is {MAX_UPLOAD_BYTES} bytes"})
    try:
        transactions, rejected, warnings = parse_upload(content, filename)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, detail={"code": "invalid_dataset", "message": str(exc)}) from exc
    if not transactions:
        raise HTTPException(status_code=422, detail={
            "code": "no_valid_transactions", "message": "No valid rows were found",
            "rejected_rows": rejected[:100],
        })
    if len(transactions) > MAX_TRANSACTIONS:
        raise HTTPException(413, detail={"code": "dataset_too_large", "message": f"Maximum is {MAX_TRANSACTIONS} valid rows"})
    dataset_id = f"ds-{uuid.uuid4().hex[:12]}"
    save_dataset(dataset_id, filename, "user_upload", transactions, warnings, rejected)
    return {
        "dataset_id": dataset_id, "name": filename, "transaction_count": len(transactions),
        "rejected_count": len(rejected), "rejected_rows": rejected[:100], "warnings": warnings,
    }


@app.get("/api/v1/datasets/{dataset_id}/rejections.json")
def rejected_rows_report(dataset_id: str) -> Response:
    dataset = get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(404, detail={"code": "dataset_not_found", "message": "Dataset not found"})
    payload = json.dumps({
        "dataset_id": dataset_id,
        "rejected_count": dataset["rejected_count"],
        "rejected_rows": dataset["rejected_rows"],
    }, ensure_ascii=False)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="graphsentinel-errors-{dataset_id}.json"'},
    )


@app.post("/api/v1/analysis/run", status_code=202)
def run_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    if get_dataset(request.dataset_id) is None:
        raise HTTPException(404, detail={"code": "dataset_not_found", "message": "Dataset not found"})
    try:
        config = validate_config(request.config)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_detector_config", "message": str(exc)}) from exc
    analysis_id = f"an-{uuid.uuid4().hex[:12]}"
    save_analysis(analysis_id, request.dataset_id)
    background_tasks.add_task(_run_analysis, analysis_id, request.dataset_id, config)
    return {"analysis_id": analysis_id, "dataset_id": request.dataset_id, "status": "running"}


def _analysis_or_404(analysis_id: str) -> dict[str, Any]:
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(404, detail={"code": "analysis_not_found", "message": "Analysis not found"})
    return analysis


@app.get("/api/v1/analysis/history")
def analysis_history(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    items = list_analyses(limit)
    return {"items": items, "total": len(items)}


@app.get("/api/v1/analysis/{analysis_id}")
def analysis_status(analysis_id: str) -> dict[str, Any]:
    analysis = _analysis_or_404(analysis_id)
    return {key: analysis[key] for key in ("analysis_id", "dataset_id", "status", "created_at", "error")} | {
        "summary": analysis["result"]["summary"] if analysis["result"] else None,
    }


@app.get("/api/v1/analysis/{analysis_id}/feedback")
def feedback_list(analysis_id: str) -> dict[str, Any]:
    _analysis_or_404(analysis_id)
    items = list_feedback(analysis_id)
    return {"items": items, "total": len(items)}


@app.post("/api/v1/analysis/{analysis_id}/feedback", status_code=201)
def feedback_create(analysis_id: str, request: PatternFeedbackRequest) -> dict[str, Any]:
    analysis = _analysis_or_404(analysis_id)
    if analysis["result"] is None:
        raise HTTPException(409, detail={"code": "analysis_not_ready", "message": "Analysis is not complete"})
    known_ids = {pattern["pattern_id"] for pattern in analysis["result"]["patterns"]}
    if request.pattern_id not in known_ids:
        raise HTTPException(404, detail={"code": "pattern_not_found", "message": "Pattern not found in this analysis"})
    return save_feedback(analysis_id, request.pattern_id, request.feedback)


@app.get("/api/v1/analysis/{analysis_id}/{section}")
def analysis_section(
    analysis_id: str,
    section: str,
    limit: int | None = None,
    offset: int = 0,
    since: datetime | None = None,
    until: datetime | None = None,
    minimum_amount: float = Query(default=0, ge=0, le=1_000_000_000_000, allow_inf_nan=False),
    account_id: str | None = Query(default=None, max_length=128),
    pattern_type: str | None = Query(default=None, max_length=64),
    risk_level: str | None = Query(default=None, max_length=16),
    ring_id: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    if section not in {"patterns", "accounts", "rings", "graph"}:
        raise HTTPException(404, detail={"code": "not_found", "message": "Analysis section not found"})
    result = _analysis_or_404(analysis_id)["result"]
    if result is None:
        raise HTTPException(409, detail={"code": "analysis_not_ready", "message": "Analysis is not complete"})
    offset = max(0, offset)
    if section == "graph":
        dataset = get_dataset(result["dataset"]["dataset_id"])
        transactions = dataset["transactions"] if dataset else []
        account_scores = {item["account_id"]: item for item in result["accounts"]}
        since_utc = since.replace(tzinfo=timezone.utc) if since and since.tzinfo is None else since
        until_utc = until.replace(tzinfo=timezone.utc) if until and until.tzinfo is None else until
        if since_utc and until_utc and since_utc > until_utc:
            raise HTTPException(422, detail={"code": "invalid_time_range", "message": "since must not be later than until"})
        if risk_level and risk_level not in {"low", "medium", "high"}:
            raise HTTPException(422, detail={"code": "invalid_risk_level", "message": "risk_level must be low, medium, or high"})
        matching_transactions = transactions
        if since_utc:
            matching_transactions = [
                tx for tx in matching_transactions
                if datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00")) >= since_utc
            ]
        if until_utc:
            matching_transactions = [
                tx for tx in matching_transactions
                if datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00")) <= until_utc
            ]
        matching_transactions = [tx for tx in matching_transactions if float(tx["amount"]) >= minimum_amount]
        if account_id:
            matching_transactions = [
                tx for tx in matching_transactions
                if account_id in (tx["source_account"], tx["destination_account"])
            ]
        if pattern_type:
            known_types = {pattern["pattern_type"] for pattern in result["patterns"]}
            if pattern_type not in known_types:
                raise HTTPException(422, detail={"code": "invalid_pattern_type", "message": "Unknown pattern type"})
            evidence_ids = {
                tx_id for pattern in result["patterns"] if pattern["pattern_type"] == pattern_type
                for tx_id in pattern["transaction_ids"]
            }
            matching_transactions = [tx for tx in matching_transactions if tx["transaction_id"] in evidence_ids]
        if ring_id:
            ring = next((item for item in result["rings"] if item["ring_id"] == ring_id), None)
            if ring is None:
                raise HTTPException(404, detail={"code": "ring_not_found", "message": "Ring not found"})
            ring_tx_ids = set(ring["transaction_ids"])
            matching_transactions = [tx for tx in matching_transactions if tx["transaction_id"] in ring_tx_ids]
        if risk_level:
            selected_accounts = {
                account for account, item in account_scores.items() if item["risk_level"] == risk_level
            }
            matching_transactions = [
                tx for tx in matching_transactions
                if tx["source_account"] in selected_accounts or tx["destination_account"] in selected_accounts
            ]
        total_edges = len(matching_transactions)
        graph_limit = max(1, min(limit if limit is not None else 1000, 1000))
        transactions = matching_transactions[:graph_limit]
        nodes = sorted({account for tx in transactions for account in (tx["source_account"], tx["destination_account"])})
        return {
            "nodes": [{"id": account, "risk_score": account_scores.get(account, {}).get("risk_score", 0),
                       "risk_level": account_scores.get(account, {}).get("risk_level", "low")} for account in nodes],
            "edges": [{"id": tx["transaction_id"], "source": tx["source_account"], "target": tx["destination_account"],
                       "amount": tx["amount"], "timestamp": tx["timestamp"]} for tx in transactions],
            "total_edges": total_edges,
            "truncated": total_edges > len(transactions),
        }
    limit = max(1, min(limit if limit is not None else 500, 1000))
    items = result[section]
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}


@app.get("/api/v1/analysis/{analysis_id}/export/json")
def export_json(analysis_id: str) -> dict[str, Any]:
    result = _analysis_or_404(analysis_id)["result"]
    if result is None:
        raise HTTPException(409, detail={"code": "analysis_not_ready", "message": "Analysis is not complete"})
    report = {"schema_version": result["schema_version"], "analysis_id": analysis_id,
              "dataset": result["dataset"], "analysis_timestamp": result["analysis_timestamp"],
              "summary": result["summary"], "patterns": result["patterns"], "accounts": result["accounts"],
              "rings": result["rings"], "model": result["model"],
              "detector_config": result["detector_config"], "warnings": result["warnings"]}
    schema_path = Path(__file__).with_name("report.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    ).iter_errors(report))
    if errors:
        logger.error("Generated report failed schema validation: %s", errors[0].message)
        raise HTTPException(500, detail={"code": "invalid_report", "message": "Report schema validation failed"})
    return report


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error at %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An unexpected server error occurred"}})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "request_validation", "message": "Request data failed validation"}},
    )
