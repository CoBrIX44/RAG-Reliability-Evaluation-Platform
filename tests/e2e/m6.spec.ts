import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const run = "11111111-1111-4111-8111-111111111111", result = "22222222-2222-4222-8222-222222222222", comparison = "33333333-3333-4333-8333-333333333333", exportId = "44444444-4444-4444-8444-444444444444";
const workspace = { stage: "baselines", api: "ready", capabilities: ["experiment_runs", "paired_comparisons", "evidence_exports", "failure_explorer"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: true, judge_configured: false };

test("read-only synthetic demo works offline, changes scenarios and opens canonical evidence without API calls", async ({ page }) => {
  const calls: string[] = [];
  await page.route("**/api/**", route => { calls.push(route.request().url()); return route.abort(); });
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "RAG Observatory · read-only demo", exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic software fixtures", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Delivered context", exact: true })).toContainText("0.0%");
  await page.getByRole("button", { name: "Gold source", exact: false }).click();
  await expect(page.getByRole("region", { name: "Original canonical source", exact: true }).locator("mark")).toHaveText("A transaction is an atomic unit.");
  await page.getByLabel("Demonstration scenario", { exact: true }).selectOption("complete");
  await expect(page.getByRole("region", { name: "Delivered context", exact: true })).toContainText("100.0%");
  await expect(page.getByText("unavailable input / unavailable output tokens", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start run", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Evaluate this answer", exact: true })).toHaveCount(0);
  expect(calls).toEqual([]);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "artifacts/m6-demo-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) { await page.setViewportSize({ width, height: 900 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); }
  await page.setViewportSize({ width: 375, height: 900 });
  await page.screenshot({ path: "artifacts/m6-demo-mobile.png", fullPage: true });
});

test("failure explorer filters diagnostics and links the exact frozen result", async ({ page }) => {
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  const requests: URL[] = [];
  await page.route("**/api/platform/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/diagnostics")) {
      requests.push(url);
      const filtered = url.searchParams.get("issue") === "context_loss";
      return route.fulfill({ json: { purpose: "development_fixture", topics: ["transactions"], difficulties: ["easy"], total_count: 2, filtered_count: filtered ? 1 : 2, next_cursor: null, issue_counts: { context_loss: 1, unavailable_assessment: 1 }, limitations: "Synthetic diagnostic signals, not benchmark outcomes.", items: [{ question_id: result, question_revision: 1, question: "Synthetic question <script>unsafe()</script>", repeat: 0, result_id: result, state: "succeeded", topic: "transactions", difficulty: "easy", issues: ["context_loss", "unavailable_assessment"] }] } });
    }
    return route.fulfill({ json: { items: [], next_cursor: null } });
  });
  await page.goto(`/runs/${run}/failures`);
  await expect(page.getByRole("heading", { name: "Failure explorer", exact: true })).toBeVisible();
  await page.getByLabel("Topic", { exact: true }).selectOption("transactions");
  await page.getByLabel("Issue", { exact: true }).selectOption("context_loss");
  await expect(page.getByText("1/2 observations match these filters.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Inspect answer and source evidence", exact: true })).toHaveAttribute("href", `/runs/${run}/results/${result}`);
  expect(requests.some(url => url.searchParams.get("topic") === "transactions" && url.searchParams.get("issue") === "context_loss")).toBe(true);
  expect(await page.locator(".failure-explorer script").count()).toBe(0);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 375, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "artifacts/m6-failures-mobile.png", fullPage: true });
});

test("evidence export preserves ambiguous retry key and is rediscovered after reload", async ({ page }) => {
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  const record = { id: comparison, state: "failed", manifest_hash: "a".repeat(64), manifest_summary: { request: { name: "Synthetic failed comparison", baseline_run_id: run, candidate_run_id: result, assessment_source: "human", exploratory: false, seed: 0, resamples: 1000 }, cutoff: "2026-10-15T00:00:00Z", baseline: {}, candidate: {} }, output: { error_code: "synthetic", error_message: "Software fixture failure" }, attempts: 1, created_at: "2026-10-15T00:00:00Z" };
  const archive = { id: exportId, state: "completed", manifest_hash: "b".repeat(64), output: { sha256: "c".repeat(64), bytes: 22 } };
  let submissions = 0;
  const keys: string[] = [];
  await page.route("**/api/platform/**", route => {
    const path = new URL(route.request().url()).pathname.replace("/api/platform/", "");
    if (path === `comparisons/${comparison}`) return route.fulfill({ json: record });
    if (path === "exports/latest") return route.fulfill({ json: submissions >= 2 ? archive : null });
    if (path === `exports/${exportId}`) return route.fulfill({ json: archive });
    if (path === "exports" && route.request().method() === "POST") {
      keys.push(route.request().headers()["idempotency-key"]);
      expect(route.request().postDataJSON()).toEqual({ source_kind: "comparison", source_id: comparison });
      return ++submissions === 1 ? route.fulfill({ status: 503, json: { message: "Synthetic ambiguous export failure" } }) : route.fulfill({ status: 202, json: { ...archive, state: "pending", output: null } });
    }
    return route.fulfill({ status: 404, json: { message: "Synthetic route missing" } });
  });
  await page.goto(`/comparisons/${comparison}`);
  await page.getByRole("button", { name: "Create evidence ZIP", exact: true }).click();
  await expect(page.locator(".export-control [role=alert]")).toContainText("Synthetic ambiguous export failure");
  await page.getByRole("button", { name: "Create evidence ZIP", exact: true }).click();
  await expect(page.getByRole("link", { name: "Download evidence ZIP", exact: true })).toHaveAttribute("href", `/api/platform/exports/${exportId}/download`);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  await page.reload();
  await expect(page.getByRole("link", { name: "Download evidence ZIP", exact: true })).toBeVisible();
  expect(submissions).toBe(2);
});
