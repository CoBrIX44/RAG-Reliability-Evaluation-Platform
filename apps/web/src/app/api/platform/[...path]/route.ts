import { NextRequest, NextResponse } from "next/server";

const allowed = /^(corpora(?:\/[0-9a-f-]{36}(?:\/(?:documents|versions))?)?|documents\/[0-9a-f-]{36}(?:\/(?:sections|retry))?|jobs\/[0-9a-f-]{36}|datasets(?:\/[0-9a-f-]{36}(?:\/(?:versions|import|questions(?:\/[0-9a-f-]{36})?))?)?|corpus-versions\/[0-9a-f-]{36}\/sections(?:\/[0-9a-f-]{36})?|dataset-versions\/[0-9a-f-]{36}\/export)$/i;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = path.join("/");
  if (!/^dense-searches\/[0-9a-f-]{36}(?:\/retry)?$/i.test(target) && !allowed.test(target) && !/^indexes(?:\/[0-9a-f-]{36}(?:\/(?:retry|search|dense-searches))?)?$/i.test(target)) return NextResponse.json({ message: "Route not found." }, { status: 404 });
  const origin = request.headers.get("origin");
  const expectedOrigin = `${request.nextUrl.protocol}//${request.headers.get("host") ?? request.nextUrl.host}`;
  if (["POST", "PATCH"].includes(request.method) && origin && origin !== expectedOrigin) {
    return NextResponse.json({ message: "Request origin is not allowed." }, { status: 403 });
  }
  try {
    const url = new URL(`/api/v1/${target}`, process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000");
    url.search = request.nextUrl.search;
    const headers = new Headers({ Accept: "application/json" });
    for (const key of ["content-type", "content-length"]) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    const options: RequestInit & { duplex?: "half" } = {
      method: request.method, headers, cache: "no-store", signal: AbortSignal.timeout(60_000),
    };
    if (["POST", "PATCH"].includes(request.method)) { options.body = request.body; options.duplex = "half"; }
    const response = await fetch(url, options);
    if (response.ok && target.endsWith("/export")) return new NextResponse(response.body, {
      headers: { "Content-Type": "application/x-ndjson", "Content-Disposition": response.headers.get("content-disposition") ?? "attachment" },
    });
    const content = await response.json();
    if (!response.ok) return NextResponse.json({
      code: typeof content.code === "string" ? content.code : "request_failed",
      message: typeof content.message === "string" ? content.message : "Check the request and try again.",
      field_errors: Array.isArray(content.field_errors) ? content.field_errors : [],
    }, { status: response.status });
    return NextResponse.json(content, { status: response.status });
  } catch {
    return NextResponse.json({ code: "api_unavailable", message: "The API is unavailable. Check workspace setup and try again." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
