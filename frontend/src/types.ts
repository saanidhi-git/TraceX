export type Dataset = {
  dataset_id: string;
  name: string;
  source: string;
  transaction_count: number;
  account_count: number;
  created_at: string;
  warnings: string[];
};

export type Pattern = {
  pattern_id: string;
  pattern_type: string;
  accounts: string[];
  transaction_ids: string[];
  severity: "low" | "medium" | "high" | "critical";
  risk_score: number;
  explanation: string;
  evidence: { amounts: number[]; transaction_count: number };
  thresholds: Record<string, number | string>;
  caveat: string;
};

export type AccountRisk = {
  account_id: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  score_type: "heuristic";
  model_anomaly_score: number | null;
  score_breakdown: Record<string, number>;
  transaction_count: number;
  transaction_volume: number;
};

export type Ring = {
  ring_id: string;
  account_ids: string[];
  transaction_ids: string[];
  patterns: string[];
  aggregate_amount: number;
  highest_risk_members: AccountRisk[];
  explanation: string;
};

export type AnalysisReport = {
  schema_version: string;
  analysis_id: string;
  dataset: Dataset;
  analysis_timestamp: string;
  summary: {
    transactions_processed: number;
    accounts_analyzed: number;
    patterns_detected: number;
    suspected_rings: number;
    high_risk_accounts: number;
    analysis_runtime_ms: number;
  };
  patterns: Pattern[];
  accounts: AccountRisk[];
  rings: Ring[];
  model: {
    name: string;
    status: string;
    training_mode?: string;
    accounts_used: number;
    score_semantics: string;
    caveat: string;
  };
  detector_config: Record<string, number>;
  warnings: string[];
};

export type GraphData = {
  nodes: { id: string; risk_score: number; risk_level: string }[];
  edges: { id: string; source: string; target: string; amount: number; timestamp: string }[];
  truncated: boolean;
  total_edges?: number;
};

export type AnalysisHistory = {
  analysis_id: string;
  dataset_id: string;
  dataset_name: string;
  status: string;
  created_at: string;
  summary: AnalysisReport["summary"] | null;
};
