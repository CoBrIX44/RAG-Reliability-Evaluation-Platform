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
const candidateSchema = z.object({ chunk_id: z.string().uuid(), rank: z.number(), score: z.number() });
export const pipelineSchema = z.object({
  fusion: z.record(z.string(), z.unknown()), candidate_k: z.number(), rrf_k: z.number(),
  lexical: z.array(candidateSchema), dense: z.array(candidateSchema), fused: z.array(candidateSchema),
  reranker: z.object({ passage_ids: z.array(z.string().uuid()), scores: z.array(z.number()), pair_tokens: z.array(z.number()), metadata: z.object({ contract: z.object({ model_id: z.string(), revision: z.string() }).passthrough() }).passthrough() }).nullable(),
  timings: z.record(z.string(), z.number()),
});
export const searchSchema = z.object({
  index_id: z.string().uuid(), strategy: z.string(), query: z.string(), returned_count: z.number(),
  embedding: z.record(z.string(), z.unknown()).nullable().optional(),
  pipeline: pipelineSchema.nullable().optional(),
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
