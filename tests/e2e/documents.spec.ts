import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const corpusId = "11111111-1111-4111-8111-111111111111";
const documentId = "22222222-2222-4222-8222-222222222222";
const jobId = "33333333-3333-4333-8333-333333333333";
const revisionId = "44444444-4444-4444-8444-444444444444";
const status = { stage: "documents", api: "ready", capabilities: ["document_ingestion", "corpus_versions"], database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" }, generation_configured: false, judge_configured: false };

test("proxy accepts its browser origin and blocks conflicting origins", async ({ request }) => {
  const local = await request.post("/api/platform/corpora", {
    headers: { Origin: "http://127.0.0.1:3000" }, data: { name: " " },
  });
  expect([422, 503]).toContain(local.status());
  const foreign = await request.post("/api/platform/corpora", {
    headers: { Origin: "https://foreign.example" }, data: { name: " " },
  });
  expect(foreign.status()).toBe(403);
});

test("create, upload, inspect evidence, and publish a corpus", async ({ page }) => {
  let created = false;
  let uploaded = false;
  let published = false;
  const corpus = { id: corpusId, name: "Test fixture corpus", description: "", draft_revision: 1, created_at: "2026-10-12T00:00:00Z" };
  const sourceDocument = { id: documentId, corpus_id: corpusId, filename: "manual.md", checksum: "a".repeat(64), byte_count: 45, state: "ready", error_message: null, job_id: jobId, section_count: 1, revision_id: revisionId };
  const version = { id: jobId, version: 1, document_count: 1, manifest_hash: "b".repeat(64), created_at: corpus.created_at };
  await page.route("**/api/workspace", route => route.fulfill({ json: status }));
  await page.route("**/api/platform/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/platform/", "");
    if (path === "corpora") {
      if (request.method() === "POST") { created = true; await route.fulfill({ status: 201, json: corpus }); }
      else await route.fulfill({ json: { items: created ? [corpus] : [], next_cursor: null } });
    } else if (path.endsWith("/documents")) {
      if (request.method() === "POST") { uploaded = true; await route.fulfill({ status: 202, json: sourceDocument }); }
      else await route.fulfill({ json: { items: uploaded ? [sourceDocument] : [], next_cursor: null } });
    } else if (path.endsWith("/versions")) {
      if (request.method() === "POST") { published = true; await route.fulfill({ status: 201, json: version }); }
      else await route.fulfill({ json: { items: published ? [version] : [], next_cursor: null } });
    } else if (path.endsWith("/sections")) {
      await route.fulfill({ json: { items: [{ id: revisionId, heading_path: ["Transactions"], text: "SELECT\n  1;\n<script>untrusted()</script>", start_offset: 0, end_offset: 45, source: { format: "markdown", start_line: 1, end_line: 4 } }], next_cursor: null } });
    } else await route.fulfill({ status: 404, json: { message: "Unknown fixture route" } });
  });
  await page.goto("/documents");
  await page.getByLabel("New corpus name").fill(corpus.name);
  await page.getByRole("button", { name: "Create corpus" }).click();
  await expect(page.getByLabel("Active corpus")).toHaveValue(corpusId);
  await page.getByLabel("Choose a technical document").setInputFiles({ name: "manual.md", mimeType: "text/markdown", buffer: Buffer.from("# Transactions\nSELECT 1;") });
  await expect(page.getByRole("button", { name: "manual.md" })).toBeVisible();
  await page.getByRole("button", { name: "manual.md" }).click();
  await expect(page.locator(".source-section pre")).toContainText("<script>untrusted()</script>");
  await expect(page.locator(".source-section script")).toHaveCount(0);
  await page.getByRole("button", { name: "Publish version" }).click();
  await expect(page.locator(".version-list")).toContainText("Version 1");
  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.getByRole("heading", { name: "Documents", exact: true }).click();
  await page.screenshot({ path: "artifacts/documents-desktop.png", fullPage: true });
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: "artifacts/documents-mobile.png", fullPage: true });
});

test("queued and failed extraction states stay actionable", async ({ page }) => {
  let failed = false;
  let retried = false;
  await page.route("**/api/workspace", route => route.fulfill({ json: { ...status, database: { ...status.database, worker_status: "stale" } } }));
  await page.route("**/api/platform/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/retry")) { retried = true; failed = false; return route.fulfill({ status: 202, json: {} }); }
    const items = path.endsWith("/corpora") ? [{ id: corpusId, name: "Failure fixture", description: "", draft_revision: 1, created_at: "2026-10-12T00:00:00Z" }]
      : path.endsWith("/documents") ? [{ id: documentId, corpus_id: corpusId, filename: "scan.pdf", checksum: "a".repeat(64), byte_count: 20, state: failed ? "failed" : "pending", error_message: failed ? "No readable text was found. Scanned PDFs need OCR first." : null, job_id: jobId, section_count: 0, revision_id: null }]
      : [];
    return route.fulfill({ json: { items, next_cursor: null } });
  });
  await page.goto("/documents");
  await expect(page.getByText("The worker is not connected.", { exact: false })).toBeVisible();
  await expect(page.getByText("Queued", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish version" })).toBeDisabled();
  failed = true;
  await expect(page.getByText("Scanned PDFs need OCR first.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Retry extraction" }).click();
  await expect(page.getByText("Extraction queued for retry.")).toBeVisible();
  expect(retried).toBe(true);
  await expect(page.getByText("Queued", { exact: true })).toBeVisible();
});

test("failed creation preserves input and a retry succeeds", async ({ page }) => {
  let fail = true;
  await page.route("**/api/workspace", route => route.fulfill({ json: status }));
  await page.route("**/api/platform/**", route => route.fulfill(route.request().method() === "POST"
    ? fail ? { status: 503, json: { message: "Database connection interrupted." } }
      : { status: 201, json: { id: corpusId, name: "Preserved name", description: "", draft_revision: 0, created_at: "2026-10-12T00:00:00Z" } }
    : { json: { items: [], next_cursor: null } }));
  await page.goto("/documents");
  await page.getByLabel("New corpus name").fill("Preserved name");
  await page.getByRole("button", { name: "Create corpus" }).click();
  await expect(page.locator(".document-workspace [role=alert]")).toContainText("Database connection interrupted");
  await expect(page.getByLabel("New corpus name")).toHaveValue("Preserved name");
  fail = false;
  await page.getByRole("button", { name: "Create corpus" }).click();
  await expect(page.getByText("Created Preserved name.")).toBeVisible();
});
