import test from "node:test";
import assert from "node:assert/strict";
import {
  loadWatchlist,
  saveWatchlist,
  WATCHLIST_KEY,
} from "../src/lib/watchlist.ts";
function store(values = {}) {
  const m = new Map(Object.entries(values));
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
}
test("existing saved matches migrate without deleting rollback data", () => {
  const s = store({ "cq-watchlist": '[4,4,-1,"5",7]' });
  assert.deepEqual(loadWatchlist(s), [4, 7]);
  assert.equal(s.getItem(WATCHLIST_KEY), "[4,7]");
  assert.equal(s.getItem("cq-watchlist"), '[4,4,-1,"5",7]');
  saveWatchlist(s, [7]);
  assert.equal(s.getItem("cq-watchlist"), "[7]");
});
test("new key wins, including an intentionally emptied watchlist", () => {
  assert.deepEqual(
    loadWatchlist(store({ [WATCHLIST_KEY]: "[]", "cq-watchlist": "[4]" })),
    [],
  );
});
test("malformed legacy data is safe and read-only storage retains saved items", () => {
  assert.deepEqual(loadWatchlist(store({ "cq-watchlist": "not json" })), []);
  const s = store({ "cq-watchlist": "[4]" });
  s.setItem = () => {
    throw Error("quota");
  };
  assert.deepEqual(loadWatchlist(s), [4]);
  assert.throws(() => saveWatchlist(s, [7]), /quota/);
});
test("denied storage reads surface to the existing warning UI", () => {
  assert.throws(
    () =>
      loadWatchlist({
        getItem: () => {
          throw Error("denied");
        },
        setItem: () => {},
      }),
    /denied/,
  );
});
