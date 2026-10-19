from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
from math import ceil
from typing import Any

import networkx as nx

from app.core.config import MAX_TRANSACTIONS
from app.ml_scoring import score_accounts


DEFAULTS = {
    "min_cycle_length": 3,
    "max_cycle_length": 5,
    "max_cycle_window_hours": 72,
    "smurf_min_counterparties": 3,
    "smurf_window_hours": 24,
    "smurf_min_total_amount": 1000.0,
    "rapid_pass_through_minutes": 60,
    "min_layered_hops": 3,
    "max_layered_window_hours": 72,
    "burst_min_transactions": 5,
    "burst_window_minutes": 30,
    "graph_transaction_limit": 50000,
    "max_findings": 500,
    "max_path_expansions": 250000,
}
FINDING_TYPES = (
    "cycle", "cyclic_mule_chain", "smurfing_fan_in", "smurfing_fan_out",
    "rapid_pass_through", "layered_multi_hop", "temporal_burst",
    "fan_in_collection", "fan_out_distribution", "cross_layer_branching",
    "shared_intermediary_rings",
)
CONFIG_BOUNDS = {
    "min_cycle_length": (2, 8),
    "max_cycle_length": (2, 8),
    "max_cycle_window_hours": (0.01, 168),
    "smurf_min_counterparties": (2, 1000),
    "smurf_window_hours": (0.01, 168),
    "smurf_min_total_amount": (0.01, 1_000_000_000_000),
    "rapid_pass_through_minutes": (1, 1440),
    "min_layered_hops": (2, 8),
    "max_layered_window_hours": (0.01, 168),
    "burst_min_transactions": (2, 50_000),
    "burst_window_minutes": (1, 10080),
    "graph_transaction_limit": (1, MAX_TRANSACTIONS),
    "max_findings": (1, 5000),
    "max_path_expansions": (100, 250000),
}


def validate_config(supplied: dict[str, Any] | None) -> dict[str, int | float]:
    validated: dict[str, int | float] = {}
    for key, default in DEFAULTS.items():
        fallback = min(default, MAX_TRANSACTIONS) if key == "graph_transaction_limit" else default
        value = (supplied or {}).get(key, fallback)
        low, high = CONFIG_BOUNDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(f"{key} must be a number between {low} and {high}")
        if isinstance(default, int):
            if not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
            validated[key] = value
        else:
            validated[key] = float(value)
    if validated["min_cycle_length"] > validated["max_cycle_length"]:
        raise ValueError("min_cycle_length cannot exceed max_cycle_length")
    return validated


def _dt(tx: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))


def _finding(kind: str, accounts: list[str], txs: list[dict[str, Any]], reason: str, severity: str, score: int,
             thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence_key = "|".join([kind, *sorted(accounts), *sorted(tx["transaction_id"] for tx in txs)])
    return {
        "pattern_id": f"pat-{sha256(evidence_key.encode()).hexdigest()[:16]}",
        "pattern_type": kind,
        "accounts": list(dict.fromkeys(accounts)),
        "transaction_ids": list(dict.fromkeys(tx["transaction_id"] for tx in txs)),
        "window_start": min((_dt(tx) for tx in txs), default=datetime.now().astimezone()).isoformat(),
        "window_end": max((_dt(tx) for tx in txs), default=datetime.now().astimezone()).isoformat(),
        "severity": severity,
        "risk_score": score,
        "explanation": reason,
        "evidence": {"amounts": [tx["amount"] for tx in txs], "transaction_count": len(txs)},
        "thresholds": thresholds or {},
        "detector_version": "1.0.0",
        "caveat": "A structural or temporal indicator is an investigative lead, not proof of financial crime.",
    }


def detect_patterns(transactions: list[dict[str, Any]], supplied: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = validate_config(supplied)
    if len(transactions) > config["graph_transaction_limit"]:
        raise ValueError(f"Dataset exceeds analysis limit ({config['graph_transaction_limit']} transactions)")
    graph = nx.MultiDiGraph()
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_destination: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tx in transactions:
        graph.add_edge(tx["source_account"], tx["destination_account"], key=tx["transaction_id"], **tx)
        by_source[tx["source_account"]].append(tx)
        by_destination[tx["destination_account"]].append(tx)
        by_account[tx["source_account"]].append(tx)
        by_account[tx["destination_account"]].append(tx)

    findings: list[dict[str, Any]] = []
    max_findings = int(config["max_findings"])
    per_type_limit = max(1, ceil(max_findings / len(FINDING_TYPES)) * 2)
    finding_counts: dict[str, int] = defaultdict(int)

    def add_finding(finding: dict[str, Any]) -> None:
        kind = finding["pattern_type"]
        if finding_counts[kind] < per_type_limit:
            findings.append(finding)
            finding_counts[kind] += 1

    # Bounded DFS avoids unbounded simple-cycle enumeration on dense graphs.
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tx in transactions:
        adjacency[tx["source_account"]].append((tx["destination_account"], tx))
    for start in sorted(adjacency):
        stack = [(start, [start], [])]
        while stack and finding_counts["cycle"] < per_type_limit:
            node, path, path_txs = stack.pop()
            if len(path_txs) >= int(config["max_cycle_length"]):
                continue
            for nxt, tx in adjacency[node]:
                if nxt == start and len(path_txs) + 1 >= int(config["min_cycle_length"]):
                    cycle_txs = path_txs + [tx]
                    times = [_dt(item) for item in cycle_txs]
                    if (max(times) - min(times)) <= timedelta(hours=float(config["max_cycle_window_hours"])):
                        cycle_finding = _finding("cycle", path + [start], cycle_txs,
                                                 "Transactions form a bounded directed cycle within the configured time window.",
                                                 "high", 85, {"min_length": config["min_cycle_length"],
                                                              "max_length": config["max_cycle_length"]})
                        add_finding(cycle_finding)
                        mule_cycle = {**cycle_finding, "pattern_type": "cyclic_mule_chain"}
                        mule_cycle["pattern_id"] = f"{cycle_finding['pattern_id']}-mule"
                        mule_cycle["explanation"] = "A cyclic transaction chain is an overlapping mule-structure indicator."
                        add_finding(mule_cycle)
                        if finding_counts["cycle"] >= per_type_limit:
                            break
                elif nxt not in path and len(path_txs) + 1 < int(config["max_cycle_length"]):
                    stack.append((nxt, path + [nxt], path_txs + [tx]))
        if finding_counts["cycle"] >= per_type_limit:
            break

    for account, inbound in by_destination.items():
        if finding_counts["smurfing_fan_in"] >= per_type_limit:
            break
        window = timedelta(hours=float(config["smurf_window_hours"]))
        ordered = sorted(inbound, key=_dt)
        for start_index, first in enumerate(ordered):
            batch = [tx for tx in ordered[start_index:] if _dt(tx) - _dt(first) <= window]
            counterparties = {tx["source_account"] for tx in batch}
            total = sum(float(tx["amount"]) for tx in batch)
            if len(counterparties) >= int(config["smurf_min_counterparties"]) and total >= float(config["smurf_min_total_amount"]):
                add_finding(_finding("smurfing_fan_in", sorted(counterparties | {account}), batch,
                                         "Multiple accounts sent funds to a common account within a short window.",
                                         "high", 78, {"min_counterparties": config["smurf_min_counterparties"],
                                                      "min_total_amount": config["smurf_min_total_amount"]}))
                break

    for account, outbound in by_source.items():
        if finding_counts["smurfing_fan_out"] >= per_type_limit:
            break
        ordered = sorted(outbound, key=_dt)
        for first in ordered:
            batch = [tx for tx in ordered if _dt(tx) >= _dt(first) and _dt(tx) - _dt(first) <= timedelta(hours=float(config["smurf_window_hours"]))]
            destinations = {tx["destination_account"] for tx in batch}
            total = sum(float(tx["amount"]) for tx in batch)
            if len(destinations) >= int(config["smurf_min_counterparties"]) and total >= float(config["smurf_min_total_amount"]):
                add_finding(_finding("smurfing_fan_out", [account, *sorted(destinations)], batch,
                                         "A common account distributed funds to multiple destinations within a short window.",
                                         "high", 76, {"min_counterparties": config["smurf_min_counterparties"],
                                                      "min_total_amount": config["smurf_min_total_amount"]}))
                break

    for account, incoming in by_destination.items():
        if finding_counts["rapid_pass_through"] >= per_type_limit:
            break
        outgoing = by_source.get(account, [])
        for arrival in incoming:
            later = [tx for tx in outgoing if timedelta(0) <= _dt(tx) - _dt(arrival) <= timedelta(minutes=float(config["rapid_pass_through_minutes"]))]
            for onward in later:
                add_finding(_finding("rapid_pass_through", [arrival["source_account"], account, onward["destination_account"]],
                                         [arrival, onward], "Funds arrived and were transferred onward shortly afterward.",
                                         "medium", 68, {"minutes": config["rapid_pass_through_minutes"]}))
                break

    # Enumerate time-ordered paths, bounded by maximum hops and per-type result cap.
    min_hops = int(config["min_layered_hops"])
    expansions = 0
    for first in transactions:
        stack = [(first["destination_account"], [first["source_account"], first["destination_account"]], [first])]
        while stack and finding_counts["layered_multi_hop"] < per_type_limit and expansions < int(config["max_path_expansions"]):
            node, path, path_txs = stack.pop()
            for nxt, tx in adjacency.get(node, []):
                expansions += 1
                if expansions >= int(config["max_path_expansions"]):
                    break
                if nxt in path or _dt(tx) < _dt(path_txs[-1]):
                    continue
                if (_dt(tx) - _dt(path_txs[0])) > timedelta(hours=float(config["max_layered_window_hours"])):
                    continue
                new_txs, new_path = path_txs + [tx], path + [nxt]
                if len(new_txs) >= min_hops:
                    add_finding(_finding("layered_multi_hop", new_path, new_txs,
                                             "A time-ordered multi-hop path moves funds through intermediary accounts.",
                                             "medium", 65, {"min_hops": min_hops,
                                                            "max_window_hours": config["max_layered_window_hours"]}))
                    break
                stack.append((nxt, new_path, new_txs))

    for account, items in by_account.items():
        if finding_counts["temporal_burst"] >= per_type_limit:
            break
        ordered = sorted(items, key=_dt)
        for first in ordered:
            batch = [tx for tx in ordered if _dt(first) <= _dt(tx) <= _dt(first) + timedelta(minutes=float(config["burst_window_minutes"]))]
            unique_ids = {tx["transaction_id"] for tx in batch}
            if len(unique_ids) >= int(config["burst_min_transactions"]):
                add_finding(_finding("temporal_burst", [account], batch,
                                         "The account has a concentrated transaction burst within the configured window.",
                                         "medium", 62, {"min_transactions": config["burst_min_transactions"],
                                                        "window_minutes": config["burst_window_minutes"]}))
                break

    # Add independent fan indicators; these findings may overlap with smurfing.
    for kind, group_map, direction in (
        ("fan_in_collection", by_destination, "in"),
        ("fan_out_distribution", by_source, "out"),
    ):
        if finding_counts[kind] >= per_type_limit:
            continue
        for account, group in group_map.items():
            if finding_counts[kind] >= per_type_limit:
                break
            counterparties = {tx["source_account"] if direction == "in" else tx["destination_account"] for tx in group}
            if len(counterparties) >= int(config["smurf_min_counterparties"]):
                add_finding(_finding(kind, sorted(counterparties | {account}), group,
                                         f"An account exhibits a {direction}-bound fan structure.",
                                         "medium", 58, {"min_counterparties": config["smurf_min_counterparties"]}))

    # Branching/reconvergence: identify shallow split-and-join motifs.
    for hub, branches in by_source.items():
        if finding_counts["cross_layer_branching"] >= per_type_limit:
            break
        branch_accounts = {tx["destination_account"] for tx in branches}
        if len(branch_accounts) < 2:
            continue
        for target, incoming in by_destination.items():
            shared = branch_accounts & {tx["source_account"] for tx in incoming}
            if len(shared) >= 2 and target != hub:
                evidence = branches + [tx for tx in incoming if tx["source_account"] in shared]
                add_finding(_finding("cross_layer_branching", sorted({hub, target, *shared}), evidence,
                                         "Funds split across branches and later reconverged at a shared destination.",
                                         "medium", 64))
                break

    # Shared intermediary evidence is grouped by accounts participating in multiple findings.
    account_patterns: dict[str, set[str]] = defaultdict(set)
    for finding in findings:
        for account in finding["accounts"]:
            account_patterns[account].add(finding["pattern_id"])
    for account, pattern_ids in account_patterns.items():
        if finding_counts["shared_intermediary_rings"] >= per_type_limit:
            break
        if len(pattern_ids) >= 2:
            add_finding(_finding("shared_intermediary_rings", [account],
                                     [tx for tx in transactions if account in (tx["source_account"], tx["destination_account"])],
                                     "The account is shared by multiple independently identified suspicious paths or structures.",
                                     "high", 72, {"minimum_overlapping_patterns": 2}))

    # Keep bounded result size, with pattern overlap explicitly exposed downstream.
    unique: dict[str, dict[str, Any]] = {}
    for finding in findings:
        unique.setdefault(finding["pattern_id"], finding)
    findings_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in unique.values():
        findings_by_type[finding["pattern_type"]].append(finding)
    balanced: list[dict[str, Any]] = []
    while len(balanced) < max_findings and any(findings_by_type.values()):
        for kind in FINDING_TYPES:
            if findings_by_type[kind] and len(balanced) < max_findings:
                balanced.append(findings_by_type[kind].pop(0))
    return balanced


def analyze(transactions: list[dict[str, Any]], dataset: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    findings = detect_patterns(transactions, config)
    model_scores, model_metadata = score_accounts(transactions)
    contributions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    account_amounts: dict[str, float] = defaultdict(float)
    account_tx_ids: dict[str, set[str]] = defaultdict(set)
    for tx in transactions:
        for account in (tx["source_account"], tx["destination_account"]):
            account_amounts[account] += float(tx["amount"])
            account_tx_ids[account].add(tx["transaction_id"])
    for finding in findings:
        for account in finding["accounts"]:
            category = {
                "cyclic_mule_chain": "cycle",
                "fan_in_collection": "smurfing_fan_in",
                "fan_out_distribution": "smurfing_fan_out",
            }.get(finding["pattern_type"], finding["pattern_type"])
            contributions[account][category] = max(
                contributions[account][category], int(finding["risk_score"])
            )
    account_scores = []
    for account in sorted(account_amounts):
        components = dict(contributions[account])
        average_strength = sum(components.values()) / max(1, len(components))
        coverage_bonus = min(20, max(0, (len(components) - 1) * 5))
        score = min(100, round(average_strength * 0.8 + coverage_bonus))
        account_scores.append({
            "account_id": account, "risk_score": score, "risk_level": "high" if score >= 70 else "medium" if score >= 40 else "low",
            "score_type": "heuristic", "score_breakdown": components,
            "model_anomaly_score": model_scores.get(account),
            "transaction_count": len(account_tx_ids[account]), "transaction_volume": round(account_amounts[account], 2),
        })
    suspicious_accounts = {account for finding in findings for account in finding["accounts"]}
    parent = {account: account for account in suspicious_accounts}
    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node
    for finding in findings:
        members = finding["accounts"]
        for member in members[1:]:
            parent[find(members[0])] = find(member)
    groups: dict[str, set[str]] = defaultdict(set)
    for account in suspicious_accounts:
        groups[find(account)].add(account)
    rings = []
    for index, members in enumerate(sorted(groups.values(), key=lambda group: sorted(group)), start=1):
        member_patterns = [item for item in findings if set(item["accounts"]) & members]
        ids = {tx_id for item in member_patterns for tx_id in item["transaction_ids"]}
        tx_map = {tx["transaction_id"]: tx for tx in transactions}
        ring_txs = [tx_map[tx_id] for tx_id in ids if tx_id in tx_map]
        rings.append({
            "ring_id": f"ring-{index}", "account_ids": sorted(members), "transaction_ids": sorted(ids),
            "patterns": sorted({item["pattern_type"] for item in member_patterns}),
            "aggregate_amount": round(sum(float(tx["amount"]) for tx in ring_txs), 2),
            "highest_risk_members": sorted(
                (item for item in account_scores if item["account_id"] in members),
                key=lambda item: item["risk_score"], reverse=True,
            )[:3],
            "explanation": "Accounts are grouped through overlapping flagged structures; connectivity does not establish coordination or criminality.",
        })
    return {
        "schema_version": "1.0.0",
        "dataset": {key: dataset[key] for key in ("dataset_id", "name", "source", "transaction_count", "account_count", "created_at", "warnings")},
        "summary": {
            "transactions_processed": len(transactions),
            "accounts_analyzed": len(account_scores),
            "patterns_detected": len(findings),
            "suspected_rings": len(rings),
            "high_risk_accounts": sum(1 for account in account_scores if account["risk_level"] == "high"),
        },
        "patterns": findings,
        "accounts": sorted(account_scores, key=lambda item: item["risk_score"], reverse=True),
        "rings": rings,
        "model": model_metadata,
        "detector_config": {**DEFAULTS, **config},
        "warnings": [
            "Risk scores are deterministic heuristic rankings, not calibrated probabilities.",
            "Detected structures are investigative leads and do not prove financial crime.",
            "Synthetic demonstration data is not representative of real-world financial activity.",
        ],
    }
