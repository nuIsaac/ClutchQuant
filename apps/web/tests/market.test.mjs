import test from "node:test";
import assert from "node:assert/strict";
import { matchesEvent, formatTime, percent } from "../src/lib/market.ts";
test("filters use actual event labels", () => {
  assert.equal(
    matchesEvent({ event_name: "VCT 2026: Americas" }, "Americas"),
    true,
  );
  assert.equal(matchesEvent({ event_name: null }, "Champions"), false);
  assert.equal(matchesEvent({ event_name: null }, "All"), true);
});
test("unknown values stay unavailable and times are readable", () => {
  assert.equal(percent(null), "—");
  assert.equal(percent(0.63), "63.0%");
  assert.equal(formatTime(null), "Unavailable");
  assert.match(formatTime("2026-09-15T12:00:00Z"), /Sep 15/);
});
