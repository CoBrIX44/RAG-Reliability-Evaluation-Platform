import { z } from "zod";

export const datasetSchema = z.object({ id: z.string().uuid(), name: z.string(), corpus_version_id: z.string().uuid(), purpose: z.enum(["research", "development_fixture"]), draft_revision: z.number() });
export const spanSchema = z.object({ section_id: z.string().uuid(), start_offset: z.number().int().nonnegative(), end_offset: z.number().int().positive() });
export const groupSchema = z.object({ fact_index: z.number().int().nonnegative(), alternatives: z.array(z.object({ spans: z.array(spanSchema).min(1) })).min(1) });
export const contentSchema = z.object({ text: z.string(), answerable: z.boolean(), reference_answer: z.string(), required_facts: z.array(z.string()), evidence_groups: z.array(groupSchema), topic: z.string(), difficulty: z.enum(["easy", "medium", "hard"]), split: z.enum(["unassigned", "development", "test"]), split_group: z.string(), review_status: z.enum(["candidate", "reviewed"]), review_source: z.enum(["human", "ai"]).default("human"), reviewer: z.string() });
export const questionSchema = z.object({ id: z.string().uuid(), dataset_id: z.string().uuid(), revision: z.number(), content: contentSchema, reviewed_at: z.string().nullable() });
export const datasetVersionSchema = z.object({ id: z.string().uuid(), version: z.number(), question_count: z.number(), manifest_hash: z.string() });
export type QuestionContent = z.infer<typeof contentSchema>;
export type Question = z.infer<typeof questionSchema>;
export type EvidenceGroup = z.infer<typeof groupSchema>;
export const emptyQuestion: QuestionContent = { text: "", answerable: true, reference_answer: "", required_facts: [], evidence_groups: [], topic: "", difficulty: "medium", split: "unassigned", split_group: "", review_status: "candidate", review_source: "human", reviewer: "" };
