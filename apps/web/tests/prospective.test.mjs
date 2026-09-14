import test from "node:test";
import assert from "node:assert/strict";
import { loadProspective } from "../src/lib/prospective.ts";
import { modelLabel } from "../src/lib/upcoming.ts";

test("unavailable prospective reports do not become zero performance", async () => {
  assert.equal(await loadProspective("http://test", async () => new Response("{}", {status:503})), null);
  assert.equal(await loadProspective("http://test", async () => Response.json({})), null);
});
test("not started is a real empty state and prospective models remain identified", async () => {
  const value = {last_run_status:"NOT_STARTED",last_run_at:null,as_of:null,records:[],models:{},counts:{},total:0};
  assert.deepEqual(await loadProspective("http://test",async () => Response.json(value)),value);
  assert.match(modelLabel("model:elo:v1:prospective-v1"),/prospective/);
  assert.match(modelLabel("model:elo:v2:decay90:prospective-v1"),/experimental/);
});
