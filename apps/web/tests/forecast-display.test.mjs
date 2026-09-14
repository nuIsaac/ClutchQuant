import assert from "node:assert/strict";
import test from "node:test";

import { getForecastDisplay } from "../src/lib/forecast-display.ts";

const match = { id: 10, team1_id: 1, team2_id: 2 };
const forecast = {
  match_id: 10,
  team1_id: 1,
  team2_id: 2,
  team1_win_probability: 0.75,
  rationale: "Elo v1 ratings: 1600.0 vs 1400.0",
};

test("unchanged participants keep their saved probability and rationale", () => {
  assert.deepEqual(getForecastDisplay(match, forecast), {
    team1Probability: 0.75,
    description: forecast.rationale,
  });
});

test("reordered teams invert probability and suppress ordered rating text", () => {
  const display = getForecastDisplay(
    { ...match, team1_id: 2, team2_id: 1 },
    forecast,
  );

  assert.equal(display.team1Probability, 0.25);
  assert.match(display.description, /current team order/);
  assert.ok(!display.description.includes(forecast.rationale));
});

test("a replaced opponent invalidates probability and rationale", () => {
  for (const participants of [
    { team1_id: 1, team2_id: 3 },
    { team1_id: 3, team2_id: 2 },
    { team1_id: 3, team2_id: 4 },
  ]) {
    const display = getForecastDisplay({ ...match, ...participants }, forecast);
    assert.equal(display.team1Probability, null);
    assert.match(display.description, /Matchup changed/);
    assert.ok(!display.description.includes(forecast.rationale));
  }
});

test("a forecast for another match cannot be displayed", () => {
  assert.equal(
    getForecastDisplay({ ...match, id: 11 }, forecast).team1Probability,
    null,
  );
});

test("unknown or duplicate team identities cannot validate a forecast", () => {
  for (const participants of [
    { team1_id: null, team2_id: 2 },
    { team1_id: 1, team2_id: null },
    { team1_id: null, team2_id: null },
    { team1_id: 1, team2_id: 1 },
  ]) {
    const display = getForecastDisplay(
      { ...match, ...participants },
      { ...forecast, ...participants },
    );
    assert.equal(display.team1Probability, null);
    assert.match(display.description, /identities are unresolved/);
  }
});

test("missing forecasts remain unknown", () => {
  assert.deepEqual(getForecastDisplay(match, undefined), {
    team1Probability: null,
    description: "No forecast recorded",
  });
});

test("zero and one probabilities are preserved and reoriented", () => {
  for (const probability of [0, 1]) {
    const snapshot = { ...forecast, team1_win_probability: probability };
    assert.equal(
      getForecastDisplay(match, snapshot).team1Probability,
      probability,
    );
    assert.equal(
      getForecastDisplay({ ...match, team1_id: 2, team2_id: 1 }, snapshot)
        .team1Probability,
      1 - probability,
    );
  }
});

test("invalid probabilities are not displayed as confidence", () => {
  for (const probability of [Number.NaN, Infinity, -0.1, 1.1]) {
    const display = getForecastDisplay(match, {
      ...forecast,
      team1_win_probability: probability,
    });
    assert.equal(display.team1Probability, null);
    assert.ok(!display.description.includes(forecast.rationale));
  }
});

test("missing rationale does not imply a missing forecast", () => {
  assert.deepEqual(getForecastDisplay(match, { ...forecast, rationale: null }), {
    team1Probability: 0.75,
    description: "Forecast available",
  });
});
