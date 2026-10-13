import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const readyStatus = {
  stage: "foundation", api: "ready", capabilities: ["health", "workspace_status"],
  database: { status: "ready", code: "ok", message: "Database and schema are ready.", worker_status: "ready" },
  generation_configured: false, judge_configured: false,
};

test("empty workspace explains capability limits and every destination works", async ({ page }) => {
  await page.route("**/api/workspace", (route) => route.fulfill({ json: readyStatus }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
  await expect(page.getByText("Execution not enabled")).toBeVisible();
  await page.getByRole("link", { name: "View setup" }).click();
  await expect(page.getByRole("heading", { name: "Workspace setup" })).toBeVisible();
  await expect(page.getByText("Not configured", { exact: true })).toHaveCount(2);
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("button", { name: "Upload document" })).toBeDisabled();
  await expect(page.getByText("Document uploads need PostgreSQL", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "Datasets", exact: true }).click();
  await expect(page.getByRole("button", { name: "Create dataset" })).toBeDisabled();
  await expect(page.getByText("Dataset curation needs PostgreSQL", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "Comparisons", exact: true }).click();
  await expect(page.getByText("Experiment execution is not enabled yet.", { exact: false })).toBeVisible();
});

test("connection errors are actionable and refresh recovers", async ({ page }) => {
  let available = false;
  await page.route("**/api/workspace", (route) => route.fulfill(available
    ? { json: readyStatus }
    : { status: 503, json: { code: "api_unavailable" } }));
  await page.goto("/settings");
  await expect(page.getByRole("status")).toContainText("The API is unavailable");
  await expect(page.getByText("Not checked", { exact: true })).toHaveCount(3);
  available = true;
  await page.getByRole("button", { name: "Refresh connection" }).click();
  await expect(page.getByRole("status")).toContainText("Database and schema are ready");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
});

test("mobile navigation and keyboard skip link work without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/workspace", (route) => route.fulfill({ json: readyStatus }));
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await page.getByRole("button", { name: "Navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Workspace" })).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Workspace setup" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});

test("core pages have no serious accessibility violations", async ({ page }) => {
  await page.route("**/api/workspace", (route) => route.fulfill({ json: readyStatus }));
  for (const path of ["/", "/settings", "/documents", "/datasets"]) {
    await page.goto(path);
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  }
});

test("unknown routes return a useful 404", async ({ page }) => {
  const response = await page.goto("/missing-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("link", { name: "Open experiments" })).toBeVisible();
});
