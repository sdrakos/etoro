import { test, expect } from "@playwright/test";

// Happy-path against the live category screener. Search/sort/pagination are
// server-side, so we assert behaviour (tab switches, rows render, controls
// present) rather than exact row counts. The backend's first catalog refresh
// can take ~60s, hence the generous load timeout.
test.describe("Screener happy path (category UI)", () => {
  test("loads Stocks, switches to Crypto, searches, paginates", async ({ page }) => {
    await page.goto("/");

    // Default category: Stocks
    await expect(
      page.getByRole("button", { name: "Stocks" })
    ).toHaveAttribute("aria-pressed", "true");

    // Wait for the first page of rows to arrive (allow for backend warm-up)
    await expect
      .poll(async () => page.locator("tbody tr").count(), { timeout: 90_000 })
      .toBeGreaterThan(0);

    // The eToro-style columns are present
    await expect(page.getByRole("columnheader", { name: "Market" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Change/ })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Sell" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Buy" })).toBeVisible();

    // Switch to Crypto → tab becomes active and rows reload
    await page.getByRole("button", { name: "Crypto" }).click();
    await expect(
      page.getByRole("button", { name: "Crypto" })
    ).toHaveAttribute("aria-pressed", "true");
    await expect
      .poll(async () => page.locator("tbody tr").count(), { timeout: 60_000 })
      .toBeGreaterThan(0);

    // Server-side search keeps rows flowing (page resets to 1)
    await page.getByPlaceholder(/search/i).fill("bit");
    await expect
      .poll(async () => page.locator("tbody tr").count(), { timeout: 30_000 })
      .toBeGreaterThan(0);

    // Pagination control is present
    await expect(
      page.getByRole("navigation", { name: "Pagination" })
    ).toBeVisible();
  });
});
