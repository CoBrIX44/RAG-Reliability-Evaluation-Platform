import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Explicitly synthetic UI checks; these are not benchmark results or human research labels.
const a = "11111111-1111-4111-8111-111111111111", b = "22222222-2222-4222-8222-222222222222", id = "33333333-3333-4333-8333-333333333333";
const created = "2026-10-15T00:00:00Z";
const request = { name: "Synthetic paired comparison", baseline_run_id: a, candidate_run_id: b, assessment_source: "human", exploratory: false, seed: 0, resamples: 1000, topics: [], difficulties: [] };
const count = { planned_count: 4, applicable_count: 4, scored_count: 4, error_count: 0, unavailable_count: 0, not_applicable_count: 0 };
const scored = { state: "scored", baseline_coverage: count, candidate_coverage: count, paired_question_count: 2, group_count: 2, excluded_question_count: 0, baseline_mean: .5, candidate_mean: .75, difference: .25, interval: { low: 0, high: .5, confidence: .95, seed: 0, resamples: 1000, resampling_unit: "split_group" }, interval_reason: null, pairs: [{ question_id: a, question: "Synthetic question <script>unsafe()</script>", group: "synthetic-group", baseline: .5, candidate: .75, difference: .25 }], exclusions: [] };
const unavailable = { ...scored, state: "unavailable", baseline_mean: null, candidate_mean: null, difference: null, interval: null, paired_question_count: 0, group_count: 0, excluded_question_count: 2, interval_reason: "No paired scores.", pairs: [], exclusions: [{ question_id: a, reason: "baseline:unavailable;candidate:unavailable" }] };
const usage = { recorded_call_count: 2, input_tokens: 100, output_tokens: 20, potential_unobserved_call_count: 1 };
const accounting = { planned_observations: 4, successful_observations: 4, failed_observations: 0, completion_rate: 1, run_elapsed_ms: 1000, queue_wait_ms: 10, stage_timings: { generation_wall_ms: { p50: 200, p95: 250, scored_count: 4, unavailable_count: 0 } }, attempt_count: 4, generation_usage: usage, judge_usage: { ...usage, recorded_call_count: 0, input_tokens: null, output_tokens: null }, measurement: { cache_condition: "not_recorded" }, index_build_ms: null, cost: { state: "unavailable", value: null, reason: "Synthetic fixture: local compute cost unmeasured." }, limitations: ["Synthetic timings, never real execution."] };
const report = { version: "paired-question-cluster-bootstrap-v1", exploratory: false, strict_blocked: false, development_fixture: true, differences: [], metrics: { retrieval_recall: scored, answer_correctness: unavailable }, accounting: { baseline: accounting, candidate: accounting }, limitations: ["Synthetic UI fixture. No research winner."] };
const record = { id, state: "completed", manifest_hash: "a".repeat(64), manifest_summary: { request, cutoff: created, baseline: {}, candidate: {} }, output: report, attempts: 1, created_at: created };
const run = (runId: string) => ({ id: runId, experiment_id: id, state: "completed", cancel_requested: false, total_count: 4, completed_count: 4, failed_count: 0, cancelled_count: 0, attempts: 1, manifest_hash: "b".repeat(64), manifest_summary: { purpose: "development_fixture", corpus_version_id: id, dataset_version_id: id, index_id: id, config: { retrieval_strategy: "hybrid" }, execution: {} }, metrics: {}, cost: null, cost_state: "unavailable", error_code: null, error_message: null, created_at: created, started_at: created, finished_at: created });

async function fixtures(page: Page) {
  await page.route("**/api/workspace", route => route.fulfill({ json: { stage: "baselines", api: "ready", capabilities: ["paired_comparisons"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: true, judge_configured: false } }));
  await page.route("**/api/platform/**", route => {
    const path = new URL(route.request().url()).pathname.replace("/api/platform/", "");
    if (path === "comparisons/facets") return route.fulfill({ json: { topics: ["transactions"], difficulties: ["easy"] } });
    if (path === "runs") return route.fulfill({ json: { items: [run(a), run(b)], next_cursor: null } });
    if (path === "comparisons") return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path === `comparisons/${id}`) return route.fulfill({ json: record });
    return route.fulfill({ json: {} });
  });
}

test("comparison form retries ambiguous submission with frozen inputs and the same key", async ({ page }) => {
  await fixtures(page);
  let submissions = 0;
  const keys: string[] = [];
  await page.route("**/api/platform/comparisons", route => {
    if (route.request().method() !== "POST") return route.fallback();
    keys.push(route.request().headers()["idempotency-key"]);
    expect(route.request().postDataJSON()).toEqual(request);
    return ++submissions === 1 ? route.fulfill({ status: 503, json: { message: "Synthetic ambiguous comparison failure" } }) : route.fulfill({ status: 202, json: { ...record, state: "pending", output: null } });
  });
  await page.goto("/comparisons");
  await page.getByLabel("Comparison name", { exact: true }).fill(request.name);
  await page.getByLabel("Baseline run", { exact: true }).selectOption(a);
  await page.getByLabel("Candidate run", { exact: true }).selectOption(b);
  await page.getByRole("button", { name: "Create comparison", exact: true }).click();
  await expect(page.locator(".comparison-workspace [role=alert]")).toContainText("Synthetic ambiguous comparison failure");
  await expect(page.getByLabel("Baseline run", { exact: true })).toHaveValue(a);
  await page.getByRole("button", { name: "Create comparison", exact: true }).click();
  await expect(page).toHaveURL(`/comparisons/${id}`);
  await expect(page.getByRole("heading", { name: request.name, exact: true })).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("paired report exposes missing scores, intervals, safe text, timing and unknown cost accessibly", async ({ page }) => {
  await fixtures(page);
  await page.goto(`/comparisons/${id}`);
  await expect(page.getByText("Development fixture · not benchmark evidence.", { exact: true })).toBeVisible();
  const chart = page.getByRole("img", { name: "Paired differences with available uncertainty", exact: true });
  await expect(chart).toBeVisible();
  await expect(chart.locator("circle")).toHaveCount(1);
  const table = page.getByRole("region", { name: "Paired quality comparison", exact: true });
  await expect(table.getByRole("row").filter({ hasText: "Retrieval recall" })).toContainText("+25.0 pp");
  await expect(table.getByRole("row").filter({ hasText: "Answer correctness" })).toContainText("unavailable");
  await expect(page.getByRole("region", { name: "baseline latency table", exact: true })).toContainText("250 ms");
  await expect(page.getByText("Cost: unavailable.", { exact: false })).toHaveCount(2);
  await page.getByLabel("Inspect metric coverage and question pairs", { exact: true }).selectOption("retrieval_recall");
  await page.getByText("Paired question means (1) and exclusions (0)", { exact: true }).click();
  await expect(page.getByText("Synthetic question <script>unsafe()</script>", { exact: true })).toBeVisible();
  expect(await page.locator(".comparison-detail script").count()).toBe(0);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "artifacts/comparison-fixture-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 375, height: 900 });
  await table.focus();
  await table.press("ArrowRight");
  await expect.poll(() => table.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  await page.screenshot({ path: "artifacts/comparison-fixture-mobile.png", fullPage: true });
});

test("partial comparison remains explicitly exploratory and strict control mismatches are visible", async ({ page }) => {
  await fixtures(page);
  await page.route(`**/api/platform/comparisons/${id}`, route => route.fulfill({ json: { ...record, manifest_summary: { ...record.manifest_summary, request: { ...request, exploratory: true } }, output: { ...report, exploratory: true, strict_blocked: true, differences: [{ field: "candidate.state", baseline: "completed", candidate: "cancelled", blocks_strict: true }] } } }));
  await page.goto(`/comparisons/${id}`);
  await expect(page.getByText("Exploratory comparison · controls or coverage may differ.", { exact: false })).toBeVisible();
  await expect(page.getByText("Controls or run completion differ.", { exact: false })).toBeVisible();
  await page.getByText("Compatibility differences (1)", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "candidate.state · blocks strict analysis", exact: true })).toBeVisible();
});
