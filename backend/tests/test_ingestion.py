import json

from app.ingestion import parse_upload


def test_csv_validation_and_duplicate_rejection():
    content = b"transaction_id,source_account,destination_account,amount,timestamp\n1,a,b,10,2025-01-01T00:00:00Z\n1,b,c,20,2025-01-01T00:01:00Z\nx,c,d,nope,bad\n"
    accepted, rejected, warnings = parse_upload(content, "test.csv")
    assert len(accepted) == 1
    assert len(rejected) == 2
    assert warnings


def test_json_array_is_supported():
    data = [{"transaction_id": "x", "source_account": "a", "destination_account": "b",
             "amount": 10, "timestamp": "2025-01-01T00:00:00Z"}]
    accepted, rejected, _ = parse_upload(json.dumps(data).encode(), "sample.json")
    assert len(accepted) == 1
    assert rejected == []


def test_json_rejects_non_object_rows_without_crashing():
    accepted, rejected, _ = parse_upload(b'[null,"invalid"]', "sample.json")
    assert accepted == []
    assert len(rejected) == 2
    assert all("must be an object" in item["error"] for item in rejected)
