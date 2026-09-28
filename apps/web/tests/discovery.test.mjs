import test from "node:test";
import assert from "node:assert/strict";
import {
  discoverMatches,
  easternDay,
  readWatchlist,
} from "../src/lib/discovery.ts";
const options = {
  query: "",
  event: "",
  day: "",
  lens: "all",
  sort: "soonest",
  savedOnly: false,
  saved: [],
};
const match = (id, p, date = "2026-09-29T01:00:00Z") => ({
  id,
  team1_name: "Team Alpha",
  team2_name: "Beta",
  event_name: "VCT Americas",
  stage: "Final",
  scheduled_at: date,
  current_preview: p === null ? null : { team1_win_probability: p },
});
test("probability sorting keeps unknown estimates last and preserves input", () => {
  const matches = [
    match(1, null),
    match(2, 0.8),
    match(3, 0.45),
    match(4, 0.3),
  ];
  assert.deepEqual(
    discoverMatches(matches, { ...options, sort: "closest" }).map((m) => m.id),
    [3, 4, 2, 1],
  );
  assert.deepEqual(
    discoverMatches(matches, { ...options, sort: "strongest" }).map(
      (m) => m.id,
    ),
    [2, 4, 3, 1],
  );
  assert.deepEqual(
    matches.map((m) => m.id),
    [1, 2, 3, 4],
  );
  assert.deepEqual(
    discoverMatches(matches, { ...options, lens: "close" }).map((m) => m.id),
    [3],
  );
  assert.deepEqual(
    discoverMatches(matches, { ...options, lens: "strong" }).map((m) => m.id),
    [2, 4],
  );
});
test("search, saved, tournament and Eastern calendar day filters combine", () => {
  const matches = [match(1, 0.5), match(2, 0.6, "2026-09-29T12:00:00Z")];
  assert.equal(easternDay(matches[0].scheduled_at), "2026-09-28");
  assert.deepEqual(
    discoverMatches(matches, {
      ...options,
      query: "  ALPHA ",
      event: "VCT Americas",
      day: "2026-09-28",
      savedOnly: true,
      saved: [1, 2],
    }).map((m) => m.id),
    [1],
  );
  assert.equal(
    discoverMatches(matches, { ...options, query: "missing" }).length,
    0,
  );
  assert.equal(
    discoverMatches(matches, { ...options, event: "different" }).length,
    0,
  );
});
test("watchlist handles corrupt and unexpected browser storage safely", () => {
  assert.deepEqual(readWatchlist("not json"), []);
  assert.deepEqual(readWatchlist('{"id":1}'), []);
  assert.deepEqual(readWatchlist(null), []);
  assert.deepEqual(readWatchlist('[1,1,2,"3",null,-1,0,1.5]'), [1, 2]);
});
