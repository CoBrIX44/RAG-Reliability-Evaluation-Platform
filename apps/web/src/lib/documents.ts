import { z } from "zod";

export const corpusSchema = z.object({ id: z.string().uuid(), name: z.string(), description: z.string(), draft_revision: z.number(), created_at: z.string() });
export const documentSchema = z.object({ id: z.string().uuid(), corpus_id: z.string().uuid(), filename: z.string(), checksum: z.string(), byte_count: z.number(), state: z.enum(["pending", "processing", "ready", "failed"]), error_message: z.string().nullable(), job_id: z.string().uuid(), section_count: z.number(), revision_id: z.string().uuid().nullable() });
export const sectionSchema = z.object({ id: z.string().uuid(), document_name: z.string().nullable().optional(), heading_path: z.array(z.string()), text: z.string(), start_offset: z.number(), end_offset: z.number(), source: z.object({ format: z.string(), page: z.number().optional(), anchor: z.string().optional(), start_line: z.number().optional(), end_line: z.number().optional() }) });
export const versionSchema = z.object({ id: z.string().uuid(), version: z.number(), document_count: z.number(), manifest_hash: z.string(), created_at: z.string() });
export const pageSchema = <T extends z.ZodType>(schema: T) => z.object({ items: z.array(schema), next_cursor: z.string().nullable() });
export type Corpus = z.infer<typeof corpusSchema>;
export type Document = z.infer<typeof documentSchema>;

export async function requestJSON(path: string, options?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api/platform/${path}`, { cache: "no-store", signal: AbortSignal.timeout(65_000), ...options });
  const body = await response.json();
  if (!response.ok) {
    const details = Array.isArray(body.field_errors) ? body.field_errors.slice(0, 8).map((item: { line?: number; field?: string; message?: string }) => `${item.line ? `Line ${item.line}: ` : item.field ? `${item.field}: ` : ""}${item.message ?? "Invalid field"}`).join("\n") : "";
    throw new Error((typeof body.message === "string" ? body.message : "The request failed.") + (details ? `\n${details}` : ""));
  }
  return body;
}

export async function allPages<T>(path: string, schema: z.ZodType<T>): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = "0";
  while (cursor !== null) {
    const page = pageSchema(schema).parse(await requestJSON(`${path}?limit=100&cursor=${cursor}`));
    items.push(...page.items);
    cursor = page.next_cursor;
  }
  return items;
}
