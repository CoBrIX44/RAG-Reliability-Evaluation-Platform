"use client";

import Link from "next/link";
import { useState } from "react";
import { QuestionTrace } from "@/components/experiments";
import { resultSchema } from "@/lib/runs";

const run = "11111111-1111-4111-8111-111111111111", question = "22222222-2222-4222-8222-222222222222", section = "33333333-3333-4333-8333-333333333333", chunk = "44444444-4444-4444-8444-444444444444";
const text = "A transaction is an atomic unit.";
const span = { section_id: section, start_offset: 0, end_offset: text.length, text_start: 0, text_end: text.length };
const passage = { id: chunk, ordinal: 0, text, token_count: 7, spans: [span] };
const scores = { state: "scored", applicable: true, precision: 1, recall: 1, returned_count: 1, relevant_passage_count: 1, covered_group_count: 1, required_group_count: 1, covered_fact_indices: [0] };

export function DemoWorkspace() {
  const [scenario, setScenario] = useState("context_loss");
  const truncated = scenario === "context_loss";
  const delivered = truncated ? { ...passage, text: "A transaction", token_count: 2, spans: [{ ...span, end_offset: 13, text_end: 13 }] } : passage;
  const result = resultSchema.parse({ id: question, run_id: run, question_id: question, question_revision: 1, repeat: 0, state: "succeeded", created_at: "2026-10-15T00:00:00Z", attempts: [], trace: {
    question: { id: question, revision: 1, reviewed_at: null, content: { text: "Synthetic demo: what is a transaction?", answerable: true, reference_answer: text, required_facts: [text], evidence_groups: [{ fact_index: 0, alternatives: [{ spans: [{ section_id: section, start_offset: 0, end_offset: text.length }] }] }], topic: "transactions", difficulty: "easy", split: "development", split_group: "synthetic-demo", review_status: "reviewed", reviewer: "Synthetic software fixture; no human benchmark review" } }, repeat: 0,
    retrieval: { index_id: run, strategy: "postgresql-lexical-v1", query: "transaction", returned_count: 1, hits: [{ rank: 1, score: .1, chunk: passage }] }, retrieval_scores: scores,
    context_scores: truncated ? { ...scores, precision: 0, recall: 0, relevant_passage_count: 0, covered_group_count: 0, covered_fact_indices: [] } : scores,
    generation: { answer: `${text} [P1]`, context: { tokenizer: "synthetic-demo", token_budget: truncated ? 2 : 16, token_count: delivered.token_count, text: delivered.text, passages: [delivered], truncated_chunk_ids: truncated ? [chunk] : [], omitted_chunk_ids: [] }, prompt: "Synthetic demonstration prompt. No model inference was performed.", prompt_hash: "d0620570b2df9ba4025f11a75e9dcd00ea7b5c0f3848aacf7f42ef5b918c5c7f", input_tokens: null, output_tokens: null, finish_reason: "eos", abstained: false, citations: ["P1"], unknown_citations: [], metadata: { software_fixture: true, usage: "Illustrative placeholders; no provider or model call" } }, timings: {},
  } });
  return <main id="main" className="demo-workspace"><Link className="text-link" href="/">← Local workspace</Link><h1>RAG Observatory · read-only demo</h1><p className="connection-message warning">Synthetic software fixtures · no measured model results, live activity, provider usage, or human research labels. This page makes no API calls and cannot submit experiments or reviews.</p><p>Follow one question from gold evidence through retrieval and context packing. Compare the complete-context scenario with a clipped context that loses the required fact.</p>
    <div className="field"><label htmlFor="demo-scenario">Demonstration scenario</label><select id="demo-scenario" value={scenario} onChange={event => setScenario(event.target.value)}><option value="context_loss">Context clipping loses required evidence</option><option value="complete">Complete evidence reaches the answer</option></select></div>
    <section aria-labelledby="demo-explanation"><h2 id="demo-explanation">What this example illustrates</h2><p>{truncated ? "Retrieval contains the whole required fact, but the context budget delivers only a prefix. Pre-packing recall is 1 and delivered-context recall is 0 under the canonical span formula. The extra content in the illustrative answer still needs a separate support assessment." : "Both retrieval and delivered context contain the annotated fact. Evidence recall is 1 in this synthetic example; answer quality still requires a separate review."}</p><p>Hand-computed fixture values illustrate the software policy. They are not benchmark accuracy or evidence of a better retrieval strategy.</p></section>
    <QuestionTrace key={scenario} result={result} corpusVersion={run} readOnly demoSources={{ [section]: { id: section, heading_path: ["Synthetic transactions"], text, document_name: "synthetic-demo.md", source: { format: "markdown" } } }} />
  </main>;
}
