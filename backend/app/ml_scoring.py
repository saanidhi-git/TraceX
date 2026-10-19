from collections import defaultdict
from typing import Any

from sklearn.ensemble import IsolationForest


def score_accounts(transactions: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any]]:
    """Fit an unsupervised, deterministic anomaly model to account-level activity features."""
    features: dict[str, list[float]] = defaultdict(lambda: [0.0] * 6)
    counterparties: dict[str, set[str]] = defaultdict(set)
    for tx in transactions:
        source, destination = tx["source_account"], tx["destination_account"]
        amount = float(tx["amount"])
        features[source][0] += 1
        features[source][1] += amount
        features[destination][2] += 1
        features[destination][3] += amount
        counterparties[source].add(destination)
        counterparties[destination].add(source)
    for account in features:
        features[account][4] = len(counterparties[account])
        features[account][5] = abs(features[account][1] - features[account][3])

    accounts = sorted(features)
    if len(accounts) < 5:
        return {}, {
            "name": "IsolationForest",
            "status": "insufficient_data",
            "accounts_used": len(accounts),
            "score_semantics": "Unavailable: at least five accounts are required.",
            "caveat": "No calibrated probability or supervised accuracy claim is available.",
        }

    matrix = [features[account] for account in accounts]
    model = IsolationForest(n_estimators=100, contamination="auto", random_state=42, n_jobs=1)
    model.fit(matrix)
    raw_scores = model.score_samples(matrix)
    ranked = sorted(range(len(accounts)), key=lambda index: (float(raw_scores[index]), accounts[index]))
    scores: dict[str, float] = {}
    denominator = max(1, len(accounts) - 1)
    for rank, index in enumerate(ranked):
        scores[accounts[index]] = round(100 * (len(accounts) - 1 - rank) / denominator, 1)
    return scores, {
        "name": "IsolationForest",
        "status": "available",
        "training_mode": "unsupervised_per_analysis",
        "accounts_used": len(accounts),
        "features": ["outgoing_count", "outgoing_volume", "incoming_count", "incoming_volume",
                     "distinct_counterparties", "in_out_volume_difference"],
        "random_state": 42,
        "score_semantics": "Within-dataset anomaly rank from 0 to 100; not a probability or calibrated risk estimate.",
        "caveat": "The model is fit on the analyzed dataset without crime labels; scores are relative to this dataset and are not accuracy-evaluated.",
    }

