import type { UpcomingMatch } from "./upcoming";
export const eventFilters = [
  "All",
  "Champions",
  "Americas",
  "EMEA",
  "Pacific",
  "China",
  "Game Changers",
];
export function matchesEvent(match: UpcomingMatch, filter: string) {
  return (
    filter === "All" ||
    (match.event_name ?? "").toLowerCase().includes(filter.toLowerCase())
  );
}
export function formatTime(value: string | null | undefined) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).format(new Date(value));
}
export function percent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}
