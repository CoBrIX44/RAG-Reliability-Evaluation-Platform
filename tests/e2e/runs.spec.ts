import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Synthetic UI fixtures, never benchmark outcomes or actual model inference.
const corpus = "11111111-1111-4111-8111-111111111111";
const dataset = "22222222-2222-4222-8222-222222222222";
const index = "33333333-3333-4333-8333-333333333333";
const experiment = "44444444-4444-4444-8444-444444444444";
const runId = "55555555-5555-4555-8555-555555555555";
const resultId = "66666666-6666-4666-8666-666666666666";
const section = "77777777-7777-4777-8777-777777777777";
const questionId = "88888888-8888-4888-8888-888888888888";
const chunkId = "99999999-9999-4999-8999-999999999999";
const created = "2026-10-13T00:00:00Z";
const workspace = { stage: "baselines", api: "ready", capabilities: ["experiment_runs", "lexical_indexing"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: true, judge_configured: false };
const content = { text: "Synthetic fixture: what is a transaction?", answerable: true, reference_answer: "An atomic unit.", required_facts: ["An atomic unit."], evidence_groups: [{ fact_index: 0, alternatives: [{ spans: [{ section_id: section, start_offset: 0, end_offset: 15 }] }] }], topic: "transactions", difficulty: "easy", split: "development", split_group: "synthetic", review_status: "reviewed", reviewer: "Synthetic software fixture reviewer" };
const span = { section_id: section, start_offset: 0, end_offset: 15, text_start: 0, text_end: 15 };
const chunk = { id: chunkId, ordinal: 0, text: "An atomic unit. <script>unsafe()</script>", token_count: 10, spans: [span] };
const scores = { state: "scored", applicable: true, precision: 1, recall: 1, returned_count: 1, relevant_passage_count: 1, covered_group_count: 1, required_group_count: 1, covered_fact_indices: [0] };
const unavailable = { state: "unavailable", mean: null, applicable_count: null, scored_count: 0, error_count: 0 };
const run = { id: runId, experiment_id: experiment, state: "completed_with_errors", cancel_requested: false, total_count: 2, completed_count: 1, failed_count: 1, cancelled_count: 0, attempts: 1, manifest_hash: "a".repeat(64), manifest_summary: { purpose: "development_fixture", corpus_version_id: corpus, dataset_version_id: dataset, index_id: index, config: {}, execution: {} }, metrics: { retrieval_recall: { state: "scored", mean: 1, applicable_count: 2, scored_count: 1, error_count: 1, unavailable_count: 0 }, context_recall: { state: "scored", mean: 0, applicable_count: 2, scored_count: 1, error_count: 1, unavailable_count: 0 }, faithfulness: unavailable, answer_correctness: unavailable }, cost: null, cost_state: "unavailable", error_code: null, error_message: null, created_at: created, started_at: created, finished_at: created };
const result = { id: resultId, run_id: runId, question_id: questionId, question_revision: 2, repeat: 0, state: "succeeded", created_at: created, attempts: [], trace: { question: { id: questionId, revision: 2, content, reviewed_at: created }, repeat: 0, retrieval: { index_id: index, strategy: "pgvector-exact-cosine-v1", query: content.text, returned_count: 1, hits: [{ rank: 1, score: 0.6, chunk }] }, retrieval_scores: scores, context_scores: { ...scores, precision: 0, recall: 0, covered_group_count: 0, relevant_passage_count: 0, covered_fact_indices: [] }, generation: { answer: "Synthetic model answer <script>unsafe()</script> [P1] [P99]", context: { token_budget: 2, token_count: 2, tokenizer: "Synthetic answer tokenizer", text: "An atomic", passages: [{ ...chunk, text: "An atomic", token_count: 2, spans: [{ ...span, end_offset: 9, text_end: 9 }] }], truncated_chunk_ids: [chunkId], omitted_chunk_ids: [] }, prompt: "Synthetic prompt with evidence; no real inference.", prompt_hash: "b".repeat(64), input_tokens: 24, output_tokens: 16, finish_reason: "length", abstained: false, citations: ["P1"], unknown_citations: ["P99"], metadata: { software_fixture: true } }, timings: { retrieval_wall_ms: 2, generation_wall_ms: 10, question_wall_ms: 12 } } };

async function fixtures(page: Page, state = run.state) {
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  await page.route("**/api/platform/**", route => {
    const path = new URL(route.request().url()).pathname.replace("/api/platform/", "");
    if (path === "datasets") return route.fulfill({ json: { items: [{ id: dataset, name: "Synthetic software dataset", purpose: "development_fixture", corpus_version_id: corpus, draft_revision: 2 }], next_cursor: null } });
    if (path === `datasets/${dataset}/versions`) return route.fulfill({ json: { items: [{ id: dataset, version: 1, question_count: 2, manifest_hash: "c".repeat(64) }], next_cursor: null } });
    if (path === "indexes") return route.fulfill({ json: { items: [{ id: index, corpus_version_id: corpus, fingerprint: "d".repeat(64), config: { retrieval: "pgvector-exact-cosine-v1", chunking: { strategy: "section" } }, state: "ready", chunk_count: 1, manifest: {}, attempts: 1, error_code: null, error_message: null, created_at: created }], next_cursor: null } });
    if (path === "experiments") return route.fulfill({ json: { items: [{ id: experiment, name: "Synthetic experiment", dataset_version_id: dataset, index_id: index, config: {} }], next_cursor: null } });
    if (path === "runs") return route.fulfill({ json: { items: [{ ...run, state }], next_cursor: null } });
    if (path === `runs/${runId}`) return route.fulfill({ json: { ...run, state } });
    if (path === `runs/${runId}/results`) return route.fulfill({ json: { items: state === "running" ? [] : [{ id: resultId, question_id: questionId, question_revision: 2, repeat: 0, state: "succeeded", question: content.text, answer_preview: result.trace.generation.answer, error_code: null, retrieval_scores: scores, context_scores: result.trace.context_scores }], next_cursor: null } });
    if (path === `runs/${runId}/results/${resultId}`) return route.fulfill({ json: result });
    if (path === `runs/${runId}/attempts`) return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path.endsWith(`/sections/${section}`)) return route.fulfill({ json: { id: section, heading_path: ["Synthetic transactions"], text: chunk.text, start_offset: 0, end_offset: chunk.text.length, source: { format: "markdown" } } });
    return route.fulfill({ json: { items: [], next_cursor: null } });
  });
}

test("saved partial run exposes unavailable metrics, context loss, safe source, and usable mobile traces", async ({ page }) => {
  await fixtures(page);
  await page.goto(`/runs/${runId}`);
  await expect(page.getByRole("heading", { name: "Question trace" })).toBeVisible();
  await expect(page.getByText("Development fixture · not benchmark evidence")).toBeVisible();
  await expect(page.locator(".run-progress")).toContainText("1 failed");
  await expect(page.locator(".run-metrics tr").filter({ hasText: "Faithfulness" })).toContainText("unavailable");
  await expect(page.locator(".trace-evidence-grid")).toContainText("1 truncated · 0 omitted");
  await expect(page.getByText("The answer reached its token limit and may be incomplete.")).toBeVisible();
  await expect(page.locator(".answer-text")).toContainText("<script>unsafe()</script>");
  expect(await page.locator(".question-trace script").count()).toBe(0);
  await page.getByRole("button", { name: "Gold source", exact: false }).click();
  await expect(page.getByRole("region", { name: "Original canonical source" }).locator("mark")).toHaveText("An atomic unit.");
  await page.getByRole("link", { name: "Download frozen run manifest" }).focus();
  await expect(page.getByRole("link", { name: "Download frozen run manifest" })).toBeFocused();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "artifacts/run-fixture-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 375, height: 900 });
  await page.screenshot({ path: "artifacts/run-fixture-mobile.png", fullPage: true });
});

test("ambiguous submission preserves form and reuses its idempotency key", async ({ page }) => {
  await fixtures(page);
  let submissions = 0;
  const keys: string[] = [];
  await page.route("**/api/platform/experiments", route => route.request().method() === "POST" ? route.fulfill({ status: 201, json: { id: experiment, name: "Synthetic experiment", dataset_version_id: dataset, index_id: index, config: {} } }) : route.fallback());
  await page.route(`**/api/platform/experiments/${experiment}/runs`, route => {
    keys.push(route.request().headers()["idempotency-key"]);
    submissions++;
    return submissions === 1 ? route.fulfill({ status: 503, json: { message: "Synthetic ambiguous transport failure" } }) : route.fulfill({ status: 202, json: run });
  });
  await page.goto("/experiments");
  await page.getByLabel("Experiment name", { exact: true }).fill("Synthetic experiment");
  await page.getByRole("button", { name: "Start run", exact: true }).click();
  await expect(page.locator(".experiment-workspace [role=alert]")).toContainText("Synthetic ambiguous transport failure");
  await expect(page.getByLabel("Experiment name", { exact: true })).toHaveValue("Synthetic experiment");
  await page.getByRole("button", { name: "Start run", exact: true }).click();
  await expect(page).toHaveURL(`/runs/${runId}`);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
});

test("cancellation is cooperative and preserves the run detail route", async ({ page }) => {
  await fixtures(page, "running");
  let cancelled = false;
  await page.route(`**/api/platform/runs/${runId}`, route => route.fulfill({ json: { ...run, state: cancelled ? "cancelled" : "running", completed_count: 0, failed_count: 0, cancelled_count: cancelled ? 2 : 0, cancel_requested: cancelled } }));
  await page.route(`**/api/platform/runs/${runId}/cancel`, route => { cancelled = true; return route.fulfill({ json: { ...run, state: "cancelled", cancel_requested: true } }); });
  await page.goto(`/runs/${runId}`);
  await page.getByRole("button", { name: "Cancel run", exact: true }).click();
  await expect(page.locator(".run-progress")).toContainText("2 cancelled");
  await expect(page.getByRole("button", { name: "Cancel run", exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(`/runs/${runId}`);
});
