"use client";

type IconName =
  | "search"
  | "star"
  | "grid"
  | "list"
  | "arrow"
  | "close"
  | "live"
  | "chart"
  | "chevron"
  | "refresh";
export function Icon({
  name,
  filled = false,
}: {
  name: IconName;
  filled?: boolean;
}) {
  const paths: Record<IconName, string> = {
    search: "m21 21-4.5-4.5 M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0",
    star: "m12 3 2.8 5.7 6.3.9-4.6 4.4 1.1 6.3L12 17.3l-5.6 3 1.1-6.3L3 9.6l6.2-.9Z",
    grid: "M3 3h7v7H3Z M14 3h7v7h-7Z M3 14h7v7H3Z M14 14h7v7h-7Z",
    list: "M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    close: "m6 6 12 12M6 18 18 6",
    live: "M2 12h4l3-7 5 14 3-7h5",
    chart: "M4 19V9m8 10V4m8 15v-7",
    chevron: "m8 4 8 8-8 8",
    refresh:
      "M20 7v5h-5M4 17v-5h5M6.1 6.1a8 8 0 0 1 13.2 3M4.7 14.9a8 8 0 0 0 13.2 3",
  };
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
