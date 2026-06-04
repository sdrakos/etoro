import { describe, it, expect } from "vitest";
import { fetchCategory, fetchCatalogStatus, fetchExchanges } from "../api/screener";

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

describe("fetchExchanges", () => {
  it("returns exchange options for a category", async () => {
    const ex = await fetchExchanges("stocks");
    expect(Array.isArray(ex)).toBe(true);
    expect(ex[0]).toHaveProperty("exchange");
    expect(ex[0]).toHaveProperty("count");
  });
});

describe("fetchCategory exchange param", () => {
  it("includes exchange in the querystring when set", async () => {
    const page = await fetchCategory("stocks", { exchange: "Nasdaq" });
    expect(page.category).toBe("stocks");
  });
});
