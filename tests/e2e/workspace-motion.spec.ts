import { expect, test } from "@playwright/test";

test("workspace motion follows routes and switches to native scrolling with reduced motion", async ({ page }) => {
  await page.route("**/api/workspace", route => route.fulfill({ json: {
    stage: "foundation", api: "ready", capabilities: ["health", "workspace_status"],
    database: { status: "ready", code: "ok", message: "Ready", worker_status: "ready" },
    generation_configured: false, judge_configured: false,
  } }));
  await page.goto("/experiments");
  await expect(page.locator("html")).toHaveClass(/lenis/);
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveClass(/lenis/);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("html")).not.toHaveClass(/lenis/);
  await expect(page.locator(".page-heading > div").first()).not.toHaveAttribute("style", /opacity:\s*0/);
  const fonts = await page.getByRole("heading", { level: 1 }).evaluate(element => getComputedStyle(element).fontFamily);
  expect(fonts).toContain("instrument");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator("html")).toHaveClass(/lenis/);
  await page.getByRole("link", { name: "Read-only demo", exact: true }).click();
  await expect(page.locator("html")).not.toHaveClass(/lenis/);
});
