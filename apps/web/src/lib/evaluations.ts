import { z } from "zod";

export const claimSchema = z.object({ text: z.string(), support: z.enum(["supported", "unsupported", "uncertain"]), citations: z.array(z.string()), citations_supported: z.boolean() });
export const judgmentSchema = z.object({ facts: z.array(z.enum(["covered", "missing", "contradicted"])), claims: z.array(claimSchema), no_factual_claims: z.boolean(), rationale: z.string() });
export const answerMetricSchema = z.object({ value: z.number().nullable(), numerator: z.number().nullable(), denominator: z.number().nullable(), state: z.enum(["scored", "unavailable"]), reason: z.string().nullable() });
export const evaluationSchema = z.object({ id: z.string().uuid(), result_id: z.string().uuid(), kind: z.enum(["human", "model"]), reviewer: z.string().nullable(), manifest: z.object({ rubric: z.object({ version: z.string() }).passthrough() }).passthrough(), manifest_hash: z.string(), state: z.enum(["pending", "running", "completed", "failed"]), output: z.object({ judgment: judgmentSchema.optional(), metrics: z.record(z.string(), answerMetricSchema).optional(), error_code: z.string().optional(), error_message: z.string().optional(), raw: z.record(z.string(), z.unknown()).optional() }).nullable(), attempts: z.number(), created_at: z.string() });
export const rubricSchema = z.object({ local_judge_enabled: z.boolean(), rubric: z.record(z.string(), z.string()) });
export type Claim = z.infer<typeof claimSchema>;
export type Evaluation = z.infer<typeof evaluationSchema>;
const coverageMetricSchema = z.object({ mean: z.number().nullable(), applicable_count: z.number().nullable(), known_applicable_count: z.number(), scored_count: z.number(), error_count: z.number(), unavailable_count: z.number() });
export const evaluationCoverageSchema = z.object({ total_observations: z.number(), eligible_answers: z.number(), without_saved_answer: z.number(), selection: z.string(), sources: z.object({ human: z.record(z.string(), coverageMetricSchema), model: z.record(z.string(), coverageMetricSchema) }) });
