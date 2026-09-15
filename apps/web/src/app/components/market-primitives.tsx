import type { ReactNode } from "react";
export function ModelBadge({
  children,
  current = false,
}: {
  children: ReactNode;
  current?: boolean;
}) {
  return (
    <span
      className={`rounded px-1.5 py-1 text-[9px] font-semibold tracking-wider ${current ? "bg-violet-400/15 text-violet-300" : "bg-slate-800 text-slate-400"}`}
    >
      {children}
    </span>
  );
}
export function ProbabilityBar({
  probability,
}: {
  probability: number | null;
}) {
  if (probability === null)
    return (
      <div
        className="h-1 rounded bg-slate-800"
        aria-label="Probability unavailable"
      />
    );
  return (
    <div
      className="flex h-1 overflow-hidden rounded bg-cyan-400/40"
      aria-hidden="true"
    >
      <div
        className="h-full bg-violet-400"
        style={{ width: `${probability * 100}%` }}
      />
    </div>
  );
}
export function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="min-w-0 border-l border-slate-800 px-4 first:border-l-0">
      <p className="text-[10px] uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 font-mono text-xl font-semibold tabular-nums">
        {value}
      </p>
      {note && <p className="mt-1 text-[10px] text-slate-500">{note}</p>}
    </div>
  );
}
