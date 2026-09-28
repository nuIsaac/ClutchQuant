import test from "node:test";
import assert from "node:assert/strict";
import { recover, failedState } from "../src/lib/startup.ts";

function clock() {
  let ms = 0;
  return { now: () => ms, sleep: async wait => { ms += wait; } };
}
test("immediate API response and successful empty result", async () => {
  const c = clock();
  assert.deepEqual(await recover(async () => [], new AbortController().signal, c), []);
  assert.equal(c.now(), 0);
});
test("20 second cold start and readiness starting recover automatically", async () => {
  const c = clock(); let calls = 0;
  const result = await recover(async () => {
    calls++;
    if (c.now() < 20000) throw Error("503 starting");
    return ["match"];
  }, new AbortController().signal, c);
  assert.deepEqual(result, ["match"]);
  assert.equal(c.now(), 20000);
  assert.equal(calls, 6);
});
test("permanent outage has bounded retries", async () => {
  const c = clock(); let calls = 0;
  await assert.rejects(recover(async () => { calls++; throw Error("offline"); }, new AbortController().signal, c));
  assert.equal(c.now(), 45000);
  assert.equal(calls, 10);
});
test("failed refresh retains cached data, including valid empty data", () => {
  const data = [{ id: 1 }];
  assert.deepEqual(failedState(data), { data, phase: "error", stale: true });
  assert.equal(failedState([]).stale, true);
  assert.equal(failedState(null).stale, false);
});
test("unmount aborts recovery", async () => {
  const controller = new AbortController(); controller.abort();
  let calls = 0;
  await assert.rejects(recover(async () => { calls++; return []; }, controller.signal));
  assert.equal(calls, 0);
});
