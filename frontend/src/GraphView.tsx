import { useMemo, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import { buildGraphElements } from "./graphData";
import type { AccountRisk, AnalysisReport, GraphData, Pattern } from "./types";

export function GraphView({ data, report }: { data: GraphData; report: AnalysisReport }) {
  const [selection, setSelection] = useState<{ kind: "account" | "transaction"; id: string } | null>(null);
  const elements = useMemo(() => buildGraphElements(data), [data]);
  const selectedAccount: AccountRisk | undefined = selection?.kind === "account"
    ? report.accounts.find((account) => account.account_id === selection.id) : undefined;
  const selectedTransaction = selection?.kind === "transaction"
    ? data.edges.find((edge) => edge.id === selection.id) : undefined;
  const relatedPatterns: Pattern[] = selection?.kind === "account"
    ? report.patterns.filter((pattern) => pattern.accounts.includes(selection.id))
    : selection?.kind === "transaction"
      ? report.patterns.filter((pattern) => pattern.transaction_ids.includes(selection.id))
      : [];

  return (
    <div className="graph-wrap">
      <CytoscapeComponent
        elements={elements}
        layout={{ name: "cose", animate: false, padding: 32 }}
        stylesheet={[
          { selector: "node", style: { "background-color": "#3b82f6", label: "data(id)", color: "#172033", "font-size": "9px", "text-wrap": "wrap", "text-max-width": "80px", width: "mapData(risk, 0, 100, 24, 44)", height: "mapData(risk, 0, 100, 24, 44)", "border-width": "2px", "border-color": "#bfdbfe" } },
          { selector: 'node[level = "high"]', style: { "background-color": "#ef4444", "border-color": "#fecaca" } },
          { selector: 'node[level = "medium"]', style: { "background-color": "#f59e0b", "border-color": "#fde68a" } },
          { selector: "edge", style: { width: "2px", "line-color": "#94a3b8", "target-arrow-color": "#64748b", "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.8, label: "data(label)", color: "#475569", "font-size": "7px", "text-rotation": "autorotate" } },
          { selector: "edge.evidence", style: { width: "4px", "line-color": "#d97706", "target-arrow-color": "#d97706" } },
          { selector: ":selected", style: { "border-width": "4px", "border-color": "#d97706", "line-color": "#d97706" } },
        ]}
        style={{ width: "100%", height: "520px" }}
        cy={(cy) => cy.on("tap", "node, edge", (event) => {
          const item = event.target;
          const kind = item.isNode() ? "account" : "transaction";
          const id = item.id();
          const patterns = kind === "account"
            ? report.patterns.filter((pattern) => pattern.accounts.includes(id))
            : report.patterns.filter((pattern) => pattern.transaction_ids.includes(id));
          const transactionIds = new Set(patterns.flatMap((pattern) => pattern.transaction_ids));
          cy.edges().removeClass("evidence");
          transactionIds.forEach((transactionId) => cy.getElementById(transactionId).addClass("evidence"));
          setSelection({ kind, id });
        })}
        minZoom={0.2}
        maxZoom={3}
      />
      <div className="graph-foot">
        <span>● Low risk &nbsp; <b className="amber">●</b> Medium risk &nbsp; <b className="red">●</b> High risk</span>
        <span>Click a node or edge to inspect its related evidence.</span>
      </div>
      {selection && <div className="graph-selection">
        {selectedAccount && <>
          <strong>{selectedAccount.account_id} <span className={`risk-badge ${selectedAccount.risk_level}`}>{selectedAccount.risk_score}/100</span></strong>
          <p>Heuristic score breakdown: {Object.entries(selectedAccount.score_breakdown).map(([kind, score]) => `${kind.replace(/_/g, " ")} ${score}`).join(" · ") || "No structural finding contribution"}</p>
          <p>ML anomaly rank: {selectedAccount.model_anomaly_score ?? "not available"} · {data.edges.filter((edge) => edge.source === selection.id || edge.target === selection.id).length} related transaction(s).</p>
        </>}
        {selectedTransaction && <>
          <strong>{selectedTransaction.source} → {selectedTransaction.target} <span className="pill">{selectedTransaction.id}</span></strong>
          <p>{new Date(selectedTransaction.timestamp).toLocaleString()} · ${selectedTransaction.amount.toLocaleString()} USD</p>
        </>}
        {relatedPatterns.length ? <div className="graph-patterns">{relatedPatterns.map((pattern) => <span key={pattern.pattern_id}>{pattern.pattern_type.replace(/_/g, " ")} · {pattern.explanation}</span>)}</div> : <p>No flagged pattern directly references this selection.</p>}
      </div>}
      {data.truncated && <p className="subtle">Graph preview is limited to 1,000 transactions. Use filters before exploring larger datasets.</p>}
    </div>
  );
}
