"use client";
import { useEffect, useState } from "react";
import { decodeMatches, type UpcomingMatch } from "./upcoming";
import { recover, failedState, type DataState } from "./startup";

export function useUpcoming() {
  const [state, setState] = useState<DataState<UpcomingMatch[]>>({ data: null, phase: "loading", stale: false });
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const data = await recover(async (signal) => {
          const response = await fetch("/api/upcoming", { cache: "no-store", signal });
          if (!response.ok) throw Error("Unavailable");
          return decodeMatches(await response.json());
        }, controller.signal);
        if (!controller.signal.aborted) setState({ data, phase: "ready", stale: false });
      } catch {
        if (!controller.signal.aborted) setState(previous => failedState(previous.data));
      }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 60000);
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [generation]);
  function retry() {
    setState(previous => ({ ...previous, phase: "loading", stale: previous.data !== null }));
    setGeneration(value => value + 1);
  }
  return { ...state, retry };
}
