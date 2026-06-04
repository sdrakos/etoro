import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { useCategoryData } from "../hooks/useCategoryData";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useCategoryData", () => {
  it("fetches a category page", async () => {
    const { result } = renderHook(
      () => useCategoryData("crypto", { page: 1, pageSize: 50, sort: "change", dir: "desc" }),
      { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.category).toBe("crypto");
    expect(result.current.data?.items.length).toBeGreaterThan(0);
  });
});
