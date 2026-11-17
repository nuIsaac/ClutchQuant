import { readWatchlist } from "./discovery.ts";

export const WATCHLIST_KEY = "twelve-twelve:watchlist:v1";
// Compatibility only: retained for existing users and rollback on the same origin.
const LEGACY_KEY = "cq-watchlist";
type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;
export function loadWatchlist(storage: Storage): number[] {
  const current = storage.getItem(WATCHLIST_KEY);
  if (current !== null) return readWatchlist(current);
  const legacy = storage.getItem(LEGACY_KEY);
  const saved = readWatchlist(legacy);
  // A quota failure must not hide an otherwise readable legacy watchlist.
  if (legacy !== null) {
    try {
      storage.setItem(WATCHLIST_KEY, JSON.stringify(saved));
    } catch {
      /* retry on next write */
    }
  }
  return saved;
}
export function saveWatchlist(storage: Storage, ids: number[]): void {
  const value = JSON.stringify(readWatchlist(JSON.stringify(ids)));
  storage.setItem(WATCHLIST_KEY, value);
  // Dual-write during the transition; the new key remains authoritative.
  try {
    storage.setItem(LEGACY_KEY, value);
  } catch {
    /* new value is safely stored */
  }
}
