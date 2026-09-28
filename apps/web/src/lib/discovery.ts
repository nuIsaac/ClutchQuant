import type { UpcomingMatch } from "./upcoming";
export type BoardSort = "soonest" | "closest" | "strongest";
export type BoardLens = "all" | "close" | "strong";
export function favoriteProbability(match: UpcomingMatch) {
  const p = match.current_preview?.team1_win_probability;
  return p == null ? null : Math.max(p, 1 - p);
}
export function easternDay(date: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(date));
}
export function discoverMatches(
  matches: UpcomingMatch[],
  options: {
    query: string;
    event: string;
    day: string;
    lens: BoardLens;
    sort: BoardSort;
    savedOnly: boolean;
    saved: number[];
  },
) {
  const query = options.query.trim().toLowerCase();
  return matches
    .filter((m) => {
      const favorite = favoriteProbability(m);
      return (
        (!query ||
          `${m.team1_name} ${m.team2_name} ${m.event_name ?? ""} ${m.stage ?? ""}`
            .toLowerCase()
            .includes(query)) &&
        (!options.event || m.event_name === options.event) &&
        (!options.day || easternDay(m.scheduled_at) === options.day) &&
        (!options.savedOnly || options.saved.includes(m.id)) &&
        (options.lens === "all" ||
          (favorite !== null &&
            (options.lens === "close" ? favorite <= 0.6 : favorite >= 0.7)))
      );
    })
    .sort((a, b) => {
      if (options.sort !== "soonest") {
        const pa = favoriteProbability(a),
          pb = favoriteProbability(b);
        if (pa === null && pb !== null) return 1;
        if (pb === null && pa !== null) return -1;
        if (pa !== null && pb !== null && pa !== pb)
          return options.sort === "closest" ? pa - pb : pb - pa;
      }
      return (
        Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at) || a.id - b.id
      );
    });
}
export function readWatchlist(value: string | null): number[] {
  try {
    const items: unknown = JSON.parse(value ?? "[]");
    return Array.isArray(items)
      ? [
          ...new Set(
            items.filter(
              (id): id is number =>
                typeof id === "number" && Number.isSafeInteger(id) && id > 0,
            ),
          ),
        ]
      : [];
  } catch {
    return [];
  }
}
