import { z } from "zod";

export const indexSchema = z.object({
  id: z.string().uuid(), corpus_version_id: z.string().uuid(), fingerprint: z.string(),
  config: z.record(z.string(), z.unknown()), state: z.enum(["pending", "running", "ready", "failed"]),
  chunk_count: z.number(), manifest: z.record(z.string(), z.unknown()).nullable(), attempts: z.number(),
  error_code: z.string().nullable(), error_message: z.string().nullable(), created_at: z.string(),
});
const chunkSchema = z.object({
  id: z.string().uuid(), ordinal: z.number(), text: z.string(), token_count: z.number(),
  spans: z.array(z.object({ section_id: z.string().uuid(), start_offset: z.number(), end_offset: z.number(), text_start: z.number(), text_end: z.number() })),
});
export const searchSchema = z.object({
  index_id: z.string().uuid(), strategy: z.string(), query: z.string(), returned_count: z.number(),
  hits: z.array(z.object({ rank: z.number(), score: z.number(), chunk: chunkSchema })),
  context: z.object({ token_budget: z.number(), token_count: z.number(), tokenizer: z.string(), text: z.string(),
    passages: z.array(chunkSchema), truncated_chunk_ids: z.array(z.string()), omitted_chunk_ids: z.array(z.string()) }),
});
export type SearchResult = z.infer<typeof searchSchema>;

export const denseSearchSchema = z.object({
  id: z.string().uuid(), index_id: z.string().uuid(),
  state: z.enum(["pending", "running", "completed", "failed"]),
  request: z.object({ query: z.string(), top_k: z.number(), context_tokens: z.number() }),
  result: searchSchema.nullable(), attempts: z.number(),
  error_code: z.string().nullable(), error_message: z.string().nullable(), created_at: z.string(),
});
