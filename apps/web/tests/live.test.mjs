import test from "node:test";
import assert from "node:assert/strict";
import { decodeLive } from "../src/lib/live.ts";
const response = {
  source_status: "ok",
  items: [],
  observed_at: "2026-09-15T12:00:00Z",
  poll_seconds: 300,
  active_listed: 0,
  coverage_limit: 4,
};
test("empty live source is distinct from unavailable", () => {
  assert.equal(decodeLive(response).source_status, "ok");
  assert.equal(
    decodeLive({ ...response, source_status: "unavailable" }).source_status,
    "unavailable",
  );
});
test("bad live state cannot become a displayed probability", () => {
  assert.throws(() =>
    decodeLive({
      ...response,
      items: [{ vlr_id: 1, team1_win_probability: 1.2 }],
    }),
  );
  assert.throws(() => decodeLive({ ...response, poll_seconds: 1 }));
});
