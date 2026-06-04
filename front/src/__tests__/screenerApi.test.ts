import { describe, it, expect } from "vitest";
import { fetchCategory, fetchCatalogStatus } from "../api/screener";

describe("fetchCategory", () => {
  it("requests the category with params and returns a page", async () => {
    const page = await fetchCategory("crypto", { page: 1, pageSize: 50, sort: "change", dir: "desc" });
    expect(page.category).toBe("crypto");
    expect(page.total).toBeGreaterThan(0);
    expect(page.items[0]).toHaveProperty("sell");
    expect(page.items[0]).toHaveProperty("buy");
  });
});

describe("fetchCatalogStatus", () => {
  it("returns instrument count + age", async () => {
    const s = await fetchCatalogStatus();
    expect(typeof s.instruments).toBe("number");
  });
});
