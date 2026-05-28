import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useScreenerData } from "../hooks/useScreenerData";
import { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useScreenerData", () => {
  it("fetches sp500 rows", async () => {
    const { result } = renderHook(() => useScreenerData("sp500"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].ticker).toBe("AAPL");
  });

  it("refetches when universe changes", async () => {
    const { result, rerender } = renderHook(({ u }) => useScreenerData(u as any), {
      wrapper, initialProps: { u: "sp500" },
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.find((r) => r.ticker === "JPM")).toBeDefined();

    rerender({ u: "nasdaq100" });
    await waitFor(() =>
      expect(result.current.data?.find((r) => r.ticker === "TSLA")).toBeDefined()
    );
  });

  it("surfaces 404 as an error state", async () => {
    const { result } = renderHook(() => useScreenerData("bogus" as any), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
