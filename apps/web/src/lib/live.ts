export type LiveMatch = {
  vlr_id: number;
  status: "live" | "completed";
  team1_name: string;
  team2_name: string;
  best_of: number;
  series_score: [number, number];
  map_number: number | null;
  map_name: string | null;
  round_score: [number, number] | null;
  observed_at: string;
  source_url: string;
  raw_sha256: string;
  team1_win_probability: number | null;
  current_map_probability: number | null;
  pre_match_probability: number | null;
  team1_rating: number | null;
  team2_rating: number | null;
  history_count: number;
  model_version: string;
  reason: string | null;
};
export type LiveResponse = {
  source_status: "ok" | "partial" | "unavailable";
  items: LiveMatch[];
  observed_at: string;
  poll_seconds: number;
  active_listed: number | null;
  coverage_limit: number;
};
export function decodeLive(value: unknown): LiveResponse {
  const r = value as LiveResponse;
  const score = (v: unknown) =>
    Array.isArray(v) &&
    v.length === 2 &&
    v.every((x) => Number.isInteger(x) && x >= 0);
  const prob = (v: unknown) =>
    v === null ||
    (typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1);
  if (
    !r ||
    !["ok", "partial", "unavailable"].includes(r.source_status) ||
    !Array.isArray(r.items) ||
    !Number.isFinite(Date.parse(r.observed_at)) ||
    !Number.isInteger(r.poll_seconds) ||
    r.poll_seconds < 30 ||
    r.poll_seconds > 300
  )
    throw Error("Invalid live response");
  for (const m of r.items) {
    if (
      !Number.isInteger(m.vlr_id) ||
      !["live", "completed"].includes(m.status) ||
      typeof m.team1_name !== "string" ||
      typeof m.team2_name !== "string" ||
      !score(m.series_score) ||
      (m.round_score !== null && !score(m.round_score)) ||
      ![1, 3, 5].includes(m.best_of) ||
      !Number.isFinite(Date.parse(m.observed_at)) ||
      !prob(m.team1_win_probability) ||
      !prob(m.current_map_probability) ||
      !prob(m.pre_match_probability) ||
      (m.team1_rating !== null && !Number.isFinite(m.team1_rating)) ||
      (m.team2_rating !== null && !Number.isFinite(m.team2_rating)) ||
      (m.map_name !== null && typeof m.map_name !== "string") ||
      (m.map_number !== null &&
        (!Number.isInteger(m.map_number) || m.map_number < 1)) ||
      !Number.isInteger(m.history_count) ||
      m.history_count < 0 ||
      typeof m.model_version !== "string" ||
      (m.reason !== null && typeof m.reason !== "string")
    )
      throw Error("Invalid live match");
  }
  return r;
}
