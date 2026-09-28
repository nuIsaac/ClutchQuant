export type DataState<T> = { data: T | null; phase: "loading" | "ready" | "error"; stale: boolean };
export function failedState<T>(data: T | null): DataState<T> {
  return { data, phase: "error", stale: data !== null };
}

// The deadline includes request time as well as backoff; no concurrent retries.
export async function recover<T>(
  request: (signal: AbortSignal) => Promise<T>,
  signal: AbortSignal,
  options: { now?: () => number; sleep?: (ms: number, signal: AbortSignal) => Promise<void>; windowMs?: number } = {},
): Promise<T> {
  const now = options.now ?? Date.now;
  const sleep = options.sleep ?? ((ms, signal) => new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, ms);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  }));
  const windowMs = options.windowMs ?? 45000;
  const deadline = now() + windowMs;
  const budget = AbortSignal.any([signal, AbortSignal.timeout(windowMs)]);
  const delays = [2000, 3000, 5000];
  let attempt = 0;
  while (true) {
    budget.throwIfAborted();
    try { return await request(budget); }
    catch (error) {
      budget.throwIfAborted();
      const remaining = deadline - now();
      if (remaining <= 0) throw error;
      await sleep(Math.min(delays[Math.min(attempt++, delays.length - 1)], remaining), budget);
      if (now() >= deadline) throw error;
    }
  }
}
