import { decodeLive } from "@/lib/live";
export const dynamic = "force-dynamic";
export async function GET() {
  const base = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1";
  try {
    const response = await fetch(`${base}/matches/live`, {
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw Error("Live API unavailable");
    return Response.json(decodeLive(await response.json()), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { error: "Live feed temporarily unavailable" },
      { status: 503 },
    );
  }
}
