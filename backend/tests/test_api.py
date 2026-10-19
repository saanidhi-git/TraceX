from fastapi.testclient import TestClient

from app import storage
from app.main import app


def test_analysis_and_schema_validated_report_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        datasets = client.get("/api/v1/datasets").json()
        assert datasets
        upload = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("upload.csv", b"transaction_id,source_account,destination_account,amount,timestamp\nu1,a,b,12,2025-01-01T00:00:00Z\nu2,a,b,nope,broken\n", "text/csv")},
        )
        assert upload.status_code == 200
        assert upload.json()["transaction_count"] == 1
        assert upload.json()["rejected_count"] == 1
        assert client.get(f"/api/v1/datasets/{upload.json()['dataset_id']}").json()["preview"][0]["transaction_id"] == "u1"
        error_report = client.get(f"/api/v1/datasets/{upload.json()['dataset_id']}/rejections.json")
        assert error_report.json()["rejected_rows"][0]["row"] == 3
        invalid_config = client.post(
            "/api/v1/analysis/run",
            json={"dataset_id": datasets[0]["dataset_id"], "config": {"max_path_expansions": 10_000_000}},
        )
        assert invalid_config.status_code == 422
        started = client.post("/api/v1/analysis/run", json={"dataset_id": datasets[0]["dataset_id"]})
        assert started.status_code == 202
        analysis_id = started.json()["analysis_id"]
        status = client.get(f"/api/v1/analysis/{analysis_id}").json()
        assert status["status"] == "completed"
        assert client.get("/api/v1/analysis/history").json()["items"][0]["analysis_id"] == analysis_id
        report_response = client.get(f"/api/v1/analysis/{analysis_id}/export/json")
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["model"]["name"] == "IsolationForest"
        assert report["accounts"][0]["model_anomaly_score"] is not None
        filtered_graph = client.get(f"/api/v1/analysis/{analysis_id}/graph?minimum_amount=2000").json()
        assert filtered_graph["edges"] == []
        assert filtered_graph["total_edges"] == 0
        pattern_id = report["patterns"][0]["pattern_id"]
        feedback = client.post(
            f"/api/v1/analysis/{analysis_id}/feedback",
            json={"pattern_id": pattern_id, "feedback": "false_positive"},
        )
        assert feedback.status_code == 201
        assert client.get(f"/api/v1/analysis/{analysis_id}/feedback").json()["total"] == 1
