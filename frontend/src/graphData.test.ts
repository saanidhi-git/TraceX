import { describe, expect, it } from "vitest";
import { buildGraphElements } from "./graphData";
import type { GraphData } from "./types";

describe("buildGraphElements", () => {
  it("preserves account scores and directed transaction evidence", () => {
    const graph: GraphData = {
      nodes: [{ id: "acct-a", risk_score: 82, risk_level: "high" }],
      edges: [{ id: "tx-1", source: "acct-a", target: "acct-b", amount: 1250, timestamp: "2025-01-01T00:00:00Z" }],
      truncated: false,
    };
    expect(buildGraphElements(graph)).toEqual([
      { data: { id: "acct-a", risk: 82, level: "high" } },
      { data: { id: "tx-1", source: "acct-a", target: "acct-b", label: "$1,250", amount: 1250, timestamp: "2025-01-01T00:00:00Z" } },
    ]);
  });
});
