import { workspaceSchema } from "@/lib/workspace";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const base = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
    const response = await fetch(`${base}/api/v1/workspace`, {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!response.ok) throw new Error("API unavailable");
    const status = workspaceSchema.parse(await response.json());
    return Response.json(status, { headers: { "Cache-Control": "no-store" } });
  } catch {
    // Never relay upstream exception text, URLs, or environment values to the browser.
    return Response.json(
      { code: "api_unavailable", message: "The API is unavailable. Start the API, then retry." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
