import type { AnalysisHistory, AnalysisReport, Dataset, GraphData } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null;
    throw new Error(body?.detail?.message ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  datasets: () => request<Dataset[]>("/datasets"),
  datasetDetail: (id: string) => request<Dataset & { preview: Record<string, unknown>[]; preview_truncated: boolean }>(`/datasets/${id}`),
  rejections: (id: string) => request<{ dataset_id: string; rejected_count: number; rejected_rows: { row: number; error: string; data: unknown }[] }>(`/datasets/${id}/rejections.json`),
  upload: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ dataset_id: string; transaction_count: number; rejected_count: number; warnings: string[] }>("/datasets/upload", {
      method: "POST", body: data,
    });
  },
  startAnalysis: (dataset_id: string, config: Record<string, number>) => request<{ analysis_id: string; status: string }>("/analysis/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id, config }),
  }),
  status: (id: string) => request<{ status: string; error?: string; summary?: AnalysisReport["summary"] }>(`/analysis/${id}`),
  history: () => request<{ items: AnalysisHistory[]; total: number }>("/analysis/history"),
  feedback: (id: string) => request<{ items: { pattern_id: string; feedback: string }[]; total: number }>(`/analysis/${id}/feedback`),
  saveFeedback: (id: string, pattern_id: string, feedback: "false_positive" | "reviewed") => request("/analysis/" + id + "/feedback", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pattern_id, feedback }),
  }),
  report: (id: string) => request<AnalysisReport>(`/analysis/${id}/export/json`),
  graph: (id: string, filters: Record<string, string | number> = {}) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (String(value).length) query.set(key, String(value));
    }
    const suffix = query.size ? `?${query.toString()}` : "";
    return request<GraphData>(`/analysis/${id}/graph${suffix}`);
  },
};
