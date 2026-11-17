"use client";

export function TeamMark({
  name,
  large = false,
}: {
  name: string;
  large?: boolean;
}) {
  const words = name
    .split(/\s+/)
    .filter((w) => !["team", "esports", "gaming"].includes(w.toLowerCase()));
  const initials =
    words.length === 1
      ? words[0].slice(0, 3)
      : words
          .map((w) => w[0])
          .join("")
          .slice(0, 3) || name.slice(0, 2);
  return (
    <span className={`team-mark ${large ? "large" : ""}`}>
      {initials.toUpperCase()}
    </span>
  );
}
