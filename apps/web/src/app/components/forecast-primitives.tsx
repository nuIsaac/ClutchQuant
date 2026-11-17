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
      className={`rounded px-1.5 py-1 text-[9px] font-semibold tracking-wider ${current ? "bg-[var(--surface-subtle)] text-[var(--accent)]" : "bg-[var(--surface-subtle)] text-[var(--muted)]"}`}
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
        className="h-1 rounded bg-[var(--line)]"
        aria-label="Probability unavailable"
      />
    );
  return (
    <div
      className="flex h-1 overflow-hidden rounded bg-[var(--line)]"
      aria-hidden="true"
    >
      <div
        className="h-full bg-[var(--accent)]"
        style={{ width: `${probability * 100}%` }}
      />
    </div>
  );
}
