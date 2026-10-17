import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("landing explains the product without API calls and supports method selection", async ({ page }) => {
  const api: string[] = [];
  page.on("request", request => { if (new URL(request.url()).pathname.startsWith("/api/")) api.push(request.url()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Answers needevidence.");
  await expect(page.getByRole("link", { name: "Open workspace", exact: true }).first()).toHaveAttribute("href", "/experiments");
  await page.getByRole("button", { name: "Hybrid" }).click();
  await expect(page.getByRole("button", { name: "Hybrid" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Bring both rankings together." })).toBeVisible();
  await expect(page.getByText("Read-only demo. Synthetic evidence, not measured research results.")).toBeVisible();
  expect(api).toEqual([]);
  await expect(page.locator("html")).toHaveClass(/lenis/);
  await page.getByRole("link", { name: "Explore the demo" }).click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.locator("html")).not.toHaveClass(/lenis/);
  await expect(page.getByRole("link", { name: "Local workspace" })).toHaveAttribute("href", "/experiments");
});

test("landing opens the connected workspace and its brand returns home", async ({ page }) => {
  await page.route("**/api/workspace", route => route.fulfill({ json: {
    stage: "foundation", api: "ready", capabilities: ["health", "workspace_status"],
    database: { status: "ready", code: "ok", message: "Database and schema are ready.", worker_status: "ready" },
    generation_configured: false, judge_configured: false,
  } }));
  await page.goto("/");
  await page.getByRole("link", { name: "Open workspace", exact: true }).first().click();
  await expect(page).toHaveURL(/\/experiments$/);
  await expect(page.getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveClass(/lenis/);
  await page.getByRole("link", { name: "RAG Observatory home" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Answers needevidence.");
});

test("landing mobile, reduced motion, themes and keyboard links remain accessible", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await expect(page.locator("html")).not.toHaveClass(/lenis/);
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const dark = await new AxeBuilder({ page }).analyze();
  expect(dark.violations.filter(item => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  await page.getByLabel("Color theme").selectOption("light");
  const light = await new AxeBuilder({ page }).analyze();
  expect(light.violations.filter(item => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  await page.getByRole("link", { name: "The workflow", exact: true }).click();
  await expect(page.getByRole("button", { name: "Menu", exact: true })).toHaveAttribute("aria-expanded", "false");
});
