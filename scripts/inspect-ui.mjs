import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const output = path.resolve("artifacts");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  for (const [route, filename] of [["/", "dashboard-desktop.png"], ["/settings", "settings-desktop.png"]]) {
    await page.goto(`http://127.0.0.1:3000${route}`);
    await page.locator(".connection-pill").filter({ hasText: /API connected|API unavailable/ }).waitFor();
    await page.screenshot({ path: path.join(output, filename), fullPage: true });
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("http://127.0.0.1:3000");
  await page.locator(".connection-pill").filter({ hasText: /API connected|API unavailable/ }).waitFor();
  await page.screenshot({ path: path.join(output, "dashboard-mobile.png"), fullPage: true });
  console.log(`Rendered screenshots saved to ${output}`);
} finally {
  await browser.close();
}
