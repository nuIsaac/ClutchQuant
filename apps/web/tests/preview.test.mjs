import test from "node:test";
import assert from "node:assert/strict";
import { validPreview } from "../src/lib/upcoming.ts";

const preview = {
  source_key: "research:elo:v1:current-preview-v1",
  team1_win_probability: 0.72,
  computed_at: "2026-09-15T00:00:00Z",
  base_exported_at: "2026-09-15T00:00:00Z",
  history_count: 30000,
  dataset_sha256: "a".repeat(64),
  base_dataset_sha256: "b".repeat(64),
  team1_unseen: false,
  team2_unseen: true,
  team1_rating: 1650,
  team2_rating: 1500,
  team1_history_count: 10,
  team2_history_count: 0,
  availability: "UNKNOWN",
  used_for_prospective_scoring: false,
};
test("research preview contract forbids scoring claims and invalid probabilities", () => {
  assert.equal(validPreview(preview), true);
  for (const patch of [
    { used_for_prospective_scoring: true },
    { team1_win_probability: 1.2 },
    { availability: "OBSERVED" },
    { history_count: 0 },
  ]) {
    assert.equal(validPreview({ ...preview, ...patch }), false);
  }
});
