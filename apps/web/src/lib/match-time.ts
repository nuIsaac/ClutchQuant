export function matchTime(value: string, dateOnly = false) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    ...(dateOnly ? {} : { hour: "numeric", minute: "2-digit" }),
  }).format(new Date(value));
}
