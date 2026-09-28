import { decodeMatches } from "@/lib/upcoming";
export const dynamic = "force-dynamic";

export async function GET() {
  const base = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1";
  const signal = AbortSignal.timeout(8000);
  const headers = { "Cache-Control": "no-store" };
  try {
    const ready = await fetch(`${base}/ready`, { cache: "no-store", signal });
    if (!ready.ok || (await ready.json()).status !== "ready")
      return Response.json({ status: "starting" }, { status: 503, headers });
    const response = await fetch(`${base}/matches/upcoming/forecasts`, { cache: "no-store", signal });
    if (!response.ok)
      return Response.json({ status: "error" }, { status: 502, headers });
    return Response.json(decodeMatches(await response.json()), { headers });
  } catch {
    return Response.json({ status: "starting" }, { status: 503, headers });
  }
}
