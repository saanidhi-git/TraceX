# Detection methodology (baseline 1.0.0)

All detectors emit structural or temporal indicators, evidence transaction IDs, participants, event-time window, severity, heuristic score, thresholds, version, and a caveat. Thresholds are defaults and may be overridden with the `config` object on `POST /api/v1/analysis/run`; the API bounds every threshold and resource cap, ignores unknown keys, and rejects invalid ranges. Findings may overlap; pattern-family risk aggregation takes the maximum strength per account and family instead of summing duplicate representations of correlated evidence.

| Indicator | Default rule | Important limitation |
|---|---|---|
| Directed cycle | Bounded DFS, 3–5 edges, all transaction timestamps within 72 h | Parallel event variants and cycles are capped; cycles are not proof of circular laundering |
| Cyclic mule chain | Same cycle evidence, emitted as a separate structural indicator | Overlaps cycle detection and is not independent evidence |
| Smurfing fan-in | At least 3 distinct sources, at least $1,000 aggregate, within 24 h | The amount threshold is currency-naive; normalize currencies before cross-currency analysis |
| Smurfing fan-out | At least 3 distinct destinations, at least $1,000 aggregate, within 24 h | Same caveat; ordinary payroll/marketplaces can fan out |
| Rapid pass-through | One outgoing transaction within 60 minutes of an incoming transaction | No fund-level tracing; temporal adjacency alone is a heuristic |
| Multi-hop relay / layered path | Time-ordered path of at least 3 edges within 72 h | Paths may be enumerated repeatedly from different starting edges; result/expansion caps apply |
| Fan-in collection | At least 3 distinct senders to an account | Overlaps smurfing fan-in |
| Fan-out distribution | At least 3 distinct recipients from an account | Overlaps smurfing fan-out |
| Temporal burst | At least 5 distinct events touching an account within 30 minutes | Both inbound and outbound events count; event count is not unusualness calibrated |
| Cross-layer branching | At least two intermediary branches from a source later reconverge at one destination | Motif is shallow; no amount conservation is inferred |
| Shared-intermediary ring | Account participates in at least two different flagged pattern IDs | Indicates overlap only; connected accounts are not presumed coordinated |

The eight additional mule-structure indicators are rapid pass-through, fan-in, fan-out, multi-hop relay, cyclic mule chain, temporal burst, cross-layer branching, and shared-intermediary rings. The three general detector groups are cycle, smurfing, and layered paths; categories intentionally overlap.

## Risk score

For each account, take the maximum score among findings within each evidence family. The cycle and cyclic-mule labels share one family; fan-in/smurfing collection and fan-out/smurfing distribution also share families to avoid adding points for duplicate representations of the same structure. The account heuristic is `round(0.8 × mean(family strengths) + min(20, 5 × (family_count − 1)))`, capped to 0–100. No findings yield zero. It is a ranking heuristic, **not** a probability, calibrated estimate, or model output. ## ML anomaly estimate

Each analysis also fits a deterministic, unsupervised `IsolationForest` on per-account outgoing/incoming counts and volumes, distinct counterparty count, and in/out volume difference (random seed 42). Its output is a relative percentile rank within that dataset, not a probability and not a supervised crime prediction. At least five accounts are required. It has no crime labels, held-out evaluation, or claimed accuracy; cross-currency amount aggregation is not normalized, so use one currency or normalize before interpreting the feature values. The frontend shows the model status and account-level ML rank separately from the rule-based score.

## Safety interpretation

Flags are potential leads for qualified human review. A connected group is called a suspected transaction group, not an organization. The demo has no confirmed-crime outcome labels and does not infer legal conclusions. Thresholds need domain review and validation against a representative, appropriately governed dataset before operational use.
