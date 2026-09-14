import test from "node:test";
import assert from "node:assert/strict";
import { loadUpcoming, decodeMatches, modelLabel } from "../src/lib/upcoming.ts";

test("empty successful response remains distinct from outage", async () => {
  assert.deepEqual(await loadUpcoming("http://fixture",async () => Response.json([])),{ok:true,matches:[]});
  const failed = await loadUpcoming("http://fixture",async () => new Response("",{status:503}));
  assert.equal(failed.ok,false);
  assert.match(failed.error,/unavailable/);
});
test("network and malformed payloads produce honest unavailable state", async () => {
  assert.equal((await loadUpcoming("http://fixture",async () => { throw new Error("network"); })).ok,false);
  assert.equal((await loadUpcoming("http://fixture",async () => Response.json({matches:[]}))).ok,false);
  assert.throws(() => decodeMatches([{id:1}]),/Invalid match/);
});
test("unknown sources keep their identity and candidates are labeled", () => {
  assert.equal(modelLabel("model:unknown:v7"),"model:unknown:v7");
  assert.match(modelLabel("model:logistic:v1:observed-v1"),/experimental/);
});
