"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { z } from "zod";
import { requestJSON } from "@/lib/documents";

const schema = z.object({ id: z.string().uuid(), state: z.string(), manifest_hash: z.string(), output: z.object({ sha256: z.string().optional(), bytes: z.number().optional(), error_message: z.string().optional() }).nullable() });
export function ExportButton({ kind, id, enabled }: { kind: "run" | "comparison"; id: string; enabled: boolean }) {
  const workspace = useSWR<{ capabilities: string[] }>("/api/workspace");
  const supported = workspace.data?.capabilities.includes("evidence_exports");
  const [exportId, setExportId] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const key = useRef<string | null>(null);
  const latest = useSWR(supported && enabled && !exportId ? `exports/latest?source_kind=${kind}&source_id=${id}` : null, async (path: string) => schema.nullable().parse(await requestJSON(path)), { refreshInterval: data => data && ["pending", "running"].includes(data.state) ? 2000 : 0, shouldRetryOnError: false });
  const requested = useSWR(exportId ? `exports/${exportId}` : null, async path => schema.parse(await requestJSON(path)), { refreshInterval: data => data && ["completed", "failed"].includes(data.state) ? 0 : 2000, shouldRetryOnError: false });
  const job = exportId ? requested : latest;
  if (!supported) return null;
  const working = job.data && ["pending", "running"].includes(job.data.state);
  return <section className="export-control" aria-label="Evidence bundle export"><button className="button subtle" disabled={!enabled || busy || !!working || (!!exportId && !job.data && !job.error)} onClick={() => { key.current ??= crypto.randomUUID(); setBusy(true); setError(""); void requestJSON("exports", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key.current }, body: JSON.stringify({ source_kind: kind, source_id: id }) }).then(value => { const record = schema.parse(value); setExportId(record.id); key.current = null; }).catch(cause => setError(cause instanceof Error ? cause.message : "Export submission failed; retry uses the same key.")).finally(() => setBusy(false)); }}>{busy ? "Submitting export…" : working ? `Export ${job.data?.state}…` : "Create evidence ZIP"}</button>
    {!enabled && <p className="muted-text">Evidence exports are available after the source reaches a terminal state.</p>}
    {error && <p role="alert" className="connection-message warning">{error}</p>}
    {job.error && <p role="alert">Could not check export status. <button className="text-link" onClick={() => { void job.mutate(); }}>Retry export status</button></p>}
    {job.data?.state === "failed" && <p role="alert" className="connection-message warning">{job.data.output?.error_message ?? "Export failed. Create a new export to retry."}</p>}
    {job.data?.state === "completed" && <><a className="text-link" href={`/api/platform/exports/${job.data.id}/download`} download>Download evidence ZIP</a><p className="muted-text">{job.data.output?.bytes?.toLocaleString()} bytes · SHA-256 {job.data.output?.sha256}</p><p className="muted-text">Contains frozen inputs, raw results, assessments and available evidence. Unknown scores/cost stay unavailable. Original uploads and model weights are excluded.</p></>}
  </section>;
}
