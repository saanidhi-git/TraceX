from app.demo import demo_transactions
from app.detectors import analyze, detect_patterns, validate_config


def tx(tx_id, source, destination, minute, amount=400):
    return {
        "transaction_id": tx_id, "source_account": source, "destination_account": destination,
        "amount": amount, "currency": "USD",
        "timestamp": f"2025-01-01T00:{minute:02}:00+00:00",
    }


def test_demo_runs_all_core_patterns_and_scores_are_deterministic():
    transactions = demo_transactions()
    patterns = detect_patterns(transactions)
    types = {pattern["pattern_type"] for pattern in patterns}
    assert {"cycle", "smurfing_fan_in", "smurfing_fan_out", "rapid_pass_through",
            "layered_multi_hop", "fan_in_collection", "fan_out_distribution",
            "cyclic_mule_chain", "temporal_burst", "cross_layer_branching",
            "shared_intermediary_rings"} <= types
    dataset = {"dataset_id": "demo", "name": "demo", "source": "synthetic", "transaction_count": len(transactions),
               "account_count": 12, "created_at": "2025-01-15T10:00:00+00:00", "warnings": []}
    assert analyze(transactions, dataset, {})["accounts"] == analyze(transactions, dataset, {})["accounts"]
    assert all(account["model_anomaly_score"] is not None for account in analyze(transactions, dataset, {})["accounts"])


def test_each_additional_muling_detector_has_a_targeted_fixture():
    cases = [
        ("rapid_pass_through", [tx("r1", "a", "b", 0), tx("r2", "b", "c", 5)]),
        ("fan_in_collection", [tx("i1", "a", "x", 0), tx("i2", "b", "x", 1), tx("i3", "c", "x", 2)]),
        ("fan_out_distribution", [tx("o1", "x", "a", 0), tx("o2", "x", "b", 1), tx("o3", "x", "c", 2)]),
        ("layered_multi_hop", [tx("l1", "a", "b", 0), tx("l2", "b", "c", 1), tx("l3", "c", "d", 2)]),
        ("cyclic_mule_chain", [tx("c1", "a", "b", 0), tx("c2", "b", "c", 1), tx("c3", "c", "a", 2)]),
        ("temporal_burst", [tx(f"b{i}", "a", f"x{i}", i) for i in range(5)]),
        ("cross_layer_branching", [tx("x1", "a", "b", 0), tx("x2", "a", "c", 1),
                                   tx("x3", "b", "d", 2), tx("x4", "c", "d", 3)]),
        ("shared_intermediary_rings", [tx("s1", "a", "hub", 0), tx("s2", "b", "hub", 1),
                                        tx("s3", "c", "hub", 2), tx("s4", "hub", "out", 3)]),
    ]
    for expected_type, fixture in cases:
        assert expected_type in {item["pattern_type"] for item in detect_patterns(fixture)}, expected_type


def test_normal_transactions_do_not_trigger_structural_patterns():
    rows = [
        {"transaction_id": "a", "source_account": "one", "destination_account": "two", "amount": 10,
         "currency": "USD", "timestamp": "2025-01-01T00:00:00+00:00"},
        {"transaction_id": "b", "source_account": "three", "destination_account": "four", "amount": 20,
         "currency": "USD", "timestamp": "2025-01-03T00:00:00+00:00"},
    ]
    assert detect_patterns(rows) == []


def test_detector_configuration_enforces_resource_bounds():
    try:
        validate_config({"max_path_expansions": 10_000_000})
    except ValueError as exc:
        assert "max_path_expansions" in str(exc)
    else:
        raise AssertionError("unbounded path expansion config was accepted")
