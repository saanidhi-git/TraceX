import type { GraphData } from "./types";

export type GraphElement = {
  data: {
    id: string;
    source?: string;
    target?: string;
    risk?: number;
    level?: string;
    label?: string;
    amount?: number;
    timestamp?: string;
  };
};

export function buildGraphElements(graph: GraphData): GraphElement[] {
  return [
    ...graph.nodes.map((node) => ({ data: { id: node.id, risk: node.risk_score, level: node.risk_level } })),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: `$${edge.amount.toLocaleString()}`,
        amount: edge.amount,
        timestamp: edge.timestamp,
      },
    })),
  ];
}
