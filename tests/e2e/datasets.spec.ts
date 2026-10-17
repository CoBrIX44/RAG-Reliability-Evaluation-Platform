import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const corpusId = "11111111-1111-4111-8111-111111111111";
const versionId = "22222222-2222-4222-8222-222222222222";
const datasetId = "33333333-3333-4333-8333-333333333333";
const sectionId = "44444444-4444-4444-8444-444444444444";
const questionId = "55555555-5555-4555-8555-555555555555";
const frozenId = "66666666-6666-4666-8666-666666666666";

test("curate canonical evidence, record review, publish and export", async ({ page }) => {
  let created = false;
  let saved: Record<string, unknown> | null = null;
  let published = false;
  const source = { id: sectionId, document_name: "software-fixture.md", heading_path: ["Transactions"], text: "🧪 A transaction is a unit.", start_offset: 0, end_offset: 26, source: { format: "markdown", start_line: 1, end_line: 2 } };
  await page.route("**/api/workspace", route => route.fulfill({ json: { stage: "datasets", api: "ready", capabilities: ["document_ingestion", "dataset_curation"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: false, judge_configured: false } }));
  await page.route("**/api/platform/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/platform/", "");
    const dataset = { id: datasetId, name: "Software fixture dataset", purpose: "development_fixture", corpus_version_id: versionId, draft_revision: 1 };
    if (path === "datasets") {
      if (request.method() === "POST") { created = true; await route.fulfill({ status: 201, json: dataset }); }
      else await route.fulfill({ json: { items: created ? [dataset] : [], next_cursor: null } });
    } else if (path === "corpora") await route.fulfill({ json: { items: [{ id: corpusId, name: "Software fixture corpus", description: "", draft_revision: 1, created_at: "2026-10-12T00:00:00Z" }], next_cursor: null } });
    else if (path === `corpora/${corpusId}/versions`) await route.fulfill({ json: { items: [{ id: versionId, version: 1, document_count: 1, manifest_hash: "a".repeat(64), created_at: "2026-10-12T00:00:00Z" }], next_cursor: null } });
    else if (path === `corpus-versions/${versionId}/sections`) await route.fulfill({ json: { items: [source], next_cursor: null } });
    else if (path === `corpus-versions/${versionId}/sections/${sectionId}`) await route.fulfill({ json: source });
    else if (path === `datasets/${datasetId}/questions`) {
      if (request.method() === "POST") { saved = request.postDataJSON(); await route.fulfill({ status: 201, json: { id: questionId, dataset_id: datasetId, revision: 1, content: saved, reviewed_at: "2026-10-12T00:00:00Z" } }); }
      else await route.fulfill({ json: { items: saved ? [{ id: questionId, dataset_id: datasetId, revision: 1, content: saved, reviewed_at: "2026-10-12T00:00:00Z" }] : [], next_cursor: null } });
    } else if (path === `datasets/${datasetId}/versions`) {
      const version = { id: frozenId, version: 1, question_count: 1, manifest_hash: "b".repeat(64) };
      if (request.method() === "POST") { published = true; await route.fulfill({ status: 201, json: version }); }
      else await route.fulfill({ json: { items: published ? [version] : [], next_cursor: null } });
    } else await route.fulfill({ status: 404, json: { message: "Unknown fixture route" } });
  });
  await page.goto("/datasets");
  await page.getByLabel("New dataset name").fill("Software fixture dataset");
  await expect(page.getByLabel("Published corpus")).toHaveValue(versionId);
  await page.getByRole("button", { name: "Create dataset" }).click();
  await expect(page.getByLabel("Active dataset")).toHaveValue(datasetId);
  await page.getByLabel("Question", { exact: true }).fill("What does the test fixture say?");
  await page.getByLabel("Reference answer").fill("A transaction is a unit.");
  await page.getByLabel("Required facts · one per line").fill("A transaction is a unit.");
  await page.getByLabel("Topic", { exact: true }).fill("transactions");
  await page.getByLabel("Split", { exact: true }).selectOption("development");
  await page.getByLabel("Split group").fill("transactions-basics");
  await page.locator(".annotation-source").evaluate(element => {
    const range = document.createRange();
    range.setStart(element.firstChild!, 3);
    range.setEnd(element.firstChild!, element.textContent!.length);
    const selection = window.getSelection()!;
    selection.removeAllRanges(); selection.addRange(range);
  });
  await page.getByRole("button", { name: "Use selected text" }).click();
  await expect(page.getByLabel("Start character")).toHaveValue("2");
  await page.getByRole("button", { name: "Use whole section" }).click();
  await expect(page.getByLabel("End character · exclusive")).toHaveValue(String(Array.from(source.text).length));
  await page.getByRole("button", { name: "Add evidence passage" }).click();
  await expect(page.locator(".evidence-group pre")).toContainText(source.text);
  await page.getByLabel("I have reviewed this question, answer, and evidence").check();
  await page.getByLabel("Reviewer name").fill("Software fixture reviewer");
  await page.getByRole("button", { name: "Save question" }).click();
  await expect(page.locator(".question-list")).toContainText("Reviewed by Software fixture reviewer");
  await page.getByRole("button", { name: "Publish dataset" }).click();
  await expect(page.getByRole("link", { name: "Export JSONL" })).toHaveAttribute("href", `/api/platform/dataset-versions/${frozenId}/export`);
  await page.getByLabel("Reference answer").fill("Edited answer awaiting a fresh review.");
  await expect(page.getByLabel("I have reviewed this question, answer, and evidence")).not.toBeChecked();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations).toEqual([]);
  await page.getByRole("heading", { name: "Evaluation datasets", exact: true }).click();
  await page.screenshot({ path: "artifacts/datasets-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: "artifacts/datasets-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "What does the test fixture say?" }).click();
  await expect(page.getByLabel("I have reviewed this question, answer, and evidence")).not.toBeChecked();
});


test("AI gold review remains AI until an explicit human review is saved", async ({ page }) => {
  let content = { text: "Synthetic AI-reviewed question?", answerable: false, reference_answer: "Not enough evidence.", required_facts: [], evidence_groups: [], topic: "synthetic", difficulty: "easy", split: "unassigned", split_group: "synthetic", review_status: "reviewed", review_source: "ai", reviewer: "Synthetic AI reviewer" };
  let revision = 1;
  const submissions: Array<Record<string, unknown>> = [];
  const dataset = { id: datasetId, name: "Synthetic provenance fixture", purpose: "research", corpus_version_id: versionId, draft_revision: 1 };
  await page.route("**/api/workspace", route => route.fulfill({ json: { stage: "datasets", api: "ready", capabilities: ["dataset_curation"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: false, judge_configured: false } }));
  await page.route("**/api/platform/**", async route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace("/api/platform/", "");
    const row = () => ({ id: questionId, dataset_id: datasetId, revision, content, reviewed_at: "2026-10-16T00:00:00Z" });
    if (path === "datasets") await route.fulfill({ json: { items: [dataset], next_cursor: null } });
    else if (path === `datasets/${datasetId}/questions`) await route.fulfill({ json: { items: [row()], next_cursor: null } });
    else if (path === `datasets/${datasetId}/questions/${questionId}`) {
      const body = request.postDataJSON(); submissions.push(body.content); content = body.content; revision += 1;
      await route.fulfill({ json: row() });
    } else await route.fulfill({ json: { items: [], next_cursor: null } });
  });
  await page.goto("/datasets");
  await expect(page.locator(".question-list")).toContainText("AI · Reviewed by Synthetic AI reviewer");
  await page.getByRole("button", { name: content.text, exact: true }).click();
  const review = page.getByLabel("I have reviewed this question, answer, and evidence", { exact: true });
  await expect(review).not.toBeChecked();
  await page.getByRole("button", { name: "Save question", exact: true }).click();
  await expect.poll(() => submissions.length).toBe(1);
  expect(submissions[0].review_source).toBe("ai");
  await review.check();
  await page.getByLabel("Reviewer name", { exact: true }).fill("Synthetic human reviewer");
  await page.getByRole("button", { name: "Save question", exact: true }).click();
  await expect.poll(() => submissions.length).toBe(2);
  expect(submissions[1].review_source).toBe("human");
  await expect(page.locator(".question-list")).toContainText("Human · Reviewed by Synthetic human reviewer");
});
