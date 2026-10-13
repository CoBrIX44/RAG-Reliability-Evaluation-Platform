import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const corpusId = "11111111-1111-4111-8111-111111111111";
const versionId = "22222222-2222-4222-8222-222222222222";
const indexId = "33333333-3333-4333-8333-333333333333";
const chunkId = "44444444-4444-4444-8444-444444444444";
const sectionId = "55555555-5555-4555-8555-555555555555";
const createdAt = "2026-10-13T00:00:00Z";
const workspace = { stage: "datasets", api: "ready", capabilities: ["lexical_indexing"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: false, judge_configured: false };

test("build and inspect lexical retrieval with context truncation and source lineage", async ({ page }) => {
  let built = false;
  const index = { id: indexId, corpus_version_id: versionId, fingerprint: "a".repeat(64), config: { chunking: { strategy: "section" } }, state: "ready", chunk_count: 1, manifest: {}, attempts: 1, error_code: null, error_message: null, created_at: createdAt };
  const chunk = { id: chunkId, ordinal: 0, text: "SQL <script>untrusted()</script> 🧪 transactions", token_count: 12, spans: [{ section_id: sectionId, start_offset: 0, end_offset: 44, text_start: 0, text_end: 44 }] };
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  await page.route("**/api/platform/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/platform/", "");
    if (path === "corpora") return route.fulfill({ json: { items: [{ id: corpusId, name: "Software fixture corpus", description: "", draft_revision: 1, created_at: createdAt }], next_cursor: null } });
    if (path.endsWith("/versions")) return route.fulfill({ json: { items: [{ id: versionId, version: 1, document_count: 1, manifest_hash: "b".repeat(64), created_at: createdAt }], next_cursor: null } });
    if (path === "indexes") {
      if (route.request().method() === "POST") { built = true; return route.fulfill({ status: 202, json: index }); }
      return route.fulfill({ json: { items: built ? [index] : [], next_cursor: null } });
    }
    if (path.endsWith("/search")) return route.fulfill({ json: { index_id: indexId, strategy: "postgresql-fts-english-ts-rank-cd-v1", query: "transactions", returned_count: 1, hits: [{ rank: 1, score: 0.125, chunk }], context: { token_budget: 3, token_count: 1, tokenizer: "Software fixture tokenizer", text: "SQL", passages: [{ ...chunk, text: "SQL", token_count: 1, spans: [{ ...chunk.spans[0], end_offset: 3, text_end: 3 }] }], truncated_chunk_ids: [chunkId], omitted_chunk_ids: [] } } });
    if (path.endsWith(`/sections/${sectionId}`)) return route.fulfill({ json: { id: sectionId, document_name: "Software fixture manual.md", heading_path: ["Transactions"], text: chunk.text, start_offset: 0, end_offset: 44, source: { format: "markdown" } } });
    return route.fulfill({ status: 404, json: { message: "Unknown software fixture route" } });
  });
  await page.goto("/");
  await expect(page.getByLabel("Published corpus")).toHaveValue(versionId);
  await page.getByRole("button", { name: "Build lexical index" }).click();
  await expect(page.getByText("1 chunks ready", { exact: true })).toBeVisible();
  await page.getByLabel("Search the technical documents").fill("transactions");
  await page.getByLabel("Context token budget").fill("3");
  await page.getByRole("button", { name: "Inspect retrieval", exact: true }).click();
  await expect(page.getByText("1 / 3 tokens · 1 truncated · 0 omitted")).toBeVisible();
  await expect(page.locator(".retrieval-results pre").last()).toContainText("<script>untrusted()</script>");
  expect(await page.locator(".retrieval-results script").count()).toBe(0);
  await expect(page.locator(".retrieval-lineage")).toContainText("characters 0–44");
  await page.getByRole("button", { name: "Inspect source", exact: true }).click();
  await expect(page.getByRole("region", { name: "Canonical source excerpt" })).toContainText("Software fixture manual.md");
  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({ path: "artifacts/retrieval-fixture-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.screenshot({ path: "artifacts/retrieval-fixture-tablet.png", fullPage: true });
});

test("failed index build can be retried without losing the search query", async ({ page }) => {
  let retried = false;
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  await page.route("**/api/platform/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/retry")) { retried = true; return route.fulfill({ status: 202, json: {} }); }
    if (path.endsWith("/indexes")) return route.fulfill({ json: { items: [{ id: indexId, corpus_version_id: versionId, fingerprint: "a".repeat(64), config: {}, state: retried ? "pending" : "failed", chunk_count: 0, manifest: null, attempts: 1, error_code: "tokenizer_unavailable", error_message: retried ? null : "The pinned tokenizer is unavailable.", created_at: createdAt }], next_cursor: null } });
    return route.fulfill({ json: { items: [], next_cursor: null } });
  });
  await page.goto("/");
  await expect(page.getByText("The pinned tokenizer is unavailable.")).toBeVisible();
  await page.getByLabel("Search the technical documents").fill("transactions");
  await expect(page.getByRole("button", { name: "Inspect retrieval", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry index build" }).click();
  await expect(page.getByText("Build pending", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Search the technical documents")).toHaveValue("transactions");
});

test("dense index uses bounded chunks and queued previews recover after a failed query", async ({ page }) => {
  let built = false;
  let searched = false;
  let retried = false;
  const searchId = "66666666-6666-4666-8666-666666666666";
  const index = { id: indexId, corpus_version_id: versionId, fingerprint: "a".repeat(64), config: { retrieval: "pgvector-exact-cosine-v1", chunking: { strategy: "section" } }, state: "ready", chunk_count: 1, manifest: {}, attempts: 1, error_code: null, error_message: null, created_at: createdAt };
  const chunk = { id: chunkId, ordinal: 0, text: "Software fixture: transactions commit atomically.", token_count: 7, spans: [{ section_id: sectionId, start_offset: 0, end_offset: 47, text_start: 0, text_end: 47 }] };
  const result = { index_id: indexId, strategy: "pgvector-exact-cosine-v1", query: "atomic commit", returned_count: 1, hits: [{ rank: 1, score: 0.6, chunk }], context: { token_budget: 1024, token_count: 7, tokenizer: "Software fixture", text: chunk.text, passages: [chunk], truncated_chunk_ids: [], omitted_chunk_ids: [] } };
  const job = () => ({ id: searchId, index_id: indexId, state: retried ? "completed" : searched ? "failed" : "pending", request: { query: "atomic commit", top_k: 5, context_tokens: 1024 }, result: retried ? result : null, attempts: 1, error_code: retried ? null : "embedding_timeout", error_message: retried ? null : "Software fixture: embedding timed out.", created_at: createdAt });
  await page.route("**/api/workspace", route => route.fulfill({ json: workspace }));
  await page.route("**/api/platform/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/platform/", "");
    if (path === "corpora") return route.fulfill({ json: { items: [{ id: corpusId, name: "Software fixture corpus", description: "", draft_revision: 1, created_at: createdAt }], next_cursor: null } });
    if (path.endsWith("/versions")) return route.fulfill({ json: { items: [{ id: versionId, version: 1, document_count: 1, manifest_hash: "b".repeat(64), created_at: createdAt }], next_cursor: null } });
    if (path === "indexes") {
      if (route.request().method() === "POST") {
        expect(route.request().postDataJSON()).toMatchObject({ retrieval: "dense", chunking: { max_tokens: 254 } });
        built = true; return route.fulfill({ status: 202, json: index });
      }
      return route.fulfill({ json: { items: built ? [index] : [], next_cursor: null } });
    }
    if (path.endsWith("/dense-searches")) { searched = true; return route.fulfill({ status: 202, json: { ...job(), state: "pending" } }); }
    if (path === `dense-searches/${searchId}/retry`) { retried = true; return route.fulfill({ status: 202, json: job() }); }
    if (path === `dense-searches/${searchId}`) return route.fulfill({ json: job() });
    return route.fulfill({ status: 404, json: { message: "Unknown software fixture route" } });
  });
  await page.goto("/");
  await page.getByLabel("Retrieval method").selectOption("dense");
  await expect(page.getByLabel("Chunk token limit")).toHaveValue("254");
  await page.getByRole("button", { name: "Build dense index" }).click();
  await expect(page.getByText("1 chunks ready", { exact: true })).toBeVisible();
  await page.getByLabel("Search the technical documents").fill("atomic commit");
  await page.getByRole("button", { name: "Inspect retrieval", exact: true }).click();
  await expect(page.getByText("Software fixture: embedding timed out.")).toBeVisible();
  await expect(page.getByLabel("Search the technical documents")).toHaveValue("atomic commit");
  await page.getByRole("button", { name: "Retry dense search" }).click();
  await expect(page.getByText("Cosine similarity 0.6000 · 7 tokens")).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 375, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "artifacts/dense-fixture-mobile.png", fullPage: true });
});
