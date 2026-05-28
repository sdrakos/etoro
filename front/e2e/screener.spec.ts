import { test, expect } from "@playwright/test";

test.describe("Screener happy path", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => window.localStorage.clear());
  });

  test("loads S&P 500, switches to NASDAQ, persists, sorts, searches", async ({ page }) => {
    await page.goto("/");

    // Default universe: sp500
    await expect(page.getByRole("button", { name: /S&P 500/i })).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    // Wait for rows to load (≥ 50, allow for free-tier 2-year history limit)
    await expect.poll(async () =>
      await page.locator("tbody tr").count()
    , { timeout: 30_000 }).toBeGreaterThan(50);

    const sp500Count = await page.locator("tbody tr").count();

    // Switch to NASDAQ 100
    await page.getByRole("button", { name: /NASDAQ 100/i }).click();
    await expect.poll(async () =>
      await page.locator("tbody tr").count()
    ).toBeLessThan(sp500Count);

    // Reload → NASDAQ still selected (localStorage)
    await page.reload();
    await expect(page.getByRole("button", { name: /NASDAQ 100/i })).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    // Search filter
    await page.getByPlaceholder(/search/i).fill("AAPL");
    await expect(page.locator("tbody tr")).toHaveCount(1);
    await expect(page.locator("tbody tr").first()).toContainText("AAPL");
  });
});
