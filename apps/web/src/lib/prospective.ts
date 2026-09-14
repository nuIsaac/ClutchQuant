export type ProspectiveRecord = {
  forecast_id: number; match_id: number; source_key: string; probability: number;
  created_at: string; lock_time: string; status: string;
  outcome?: number; team1_score?: number; team2_score?: number;
};
export type ProspectiveReport = {
  last_run_status: string; last_run_at: string | null; as_of: string | null;
  counts: Record<string, number>; total: number; records: ProspectiveRecord[];
  models: Record<string, { count: number; accuracy: number; brier: number; log_loss: number; calibration_status: string }>;
};

export async function loadProspective(apiUrl: string, fetcher: typeof fetch = fetch): Promise<ProspectiveReport | null> {
  try {
    const response = await fetcher(`${apiUrl}/research/prospective?limit=50`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!response.ok) return null;
    const data = await response.json();
    if (!data || typeof data.last_run_status !== "string" || !Array.isArray(data.records) || !data.models || !data.counts || !Number.isInteger(data.total)) return null;
    for (const row of data.records) {
      if (!Number.isInteger(row.forecast_id) || !Number.isInteger(row.match_id) ||
          typeof row.source_key !== "string" || typeof row.status !== "string" ||
          !Number.isFinite(row.probability) || row.probability < 0 || row.probability > 1 ||
          !Number.isFinite(Date.parse(row.lock_time))) return null;
    }
    for (const model of Object.values(data.models) as Record<string, unknown>[]) {
      if (!model || !Number.isInteger(model.count) || !Number.isFinite(model.accuracy) ||
          !Number.isFinite(model.brier) || !Number.isFinite(model.log_loss) || typeof model.calibration_status !== "string") return null;
    }
    return data;
  } catch { return null; }
}
