import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChartView } from "../views/ChartView";

vi.mock("klinecharts", () => {
  const chart = { applyNewData: vi.fn(), createIndicator: vi.fn(() => "p"), removeIndicator: vi.fn(), updateData: vi.fn() };
  return { init: vi.fn(() => chart), dispose: vi.fn() };
});

function renderChart() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/chart/1001"]}>
        <Routes>
          <Route path="/chart/:instrumentId" element={<ChartView />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ChartView", () => {
  it("loads candles and shows the symbol header + toolbar", async () => {
    renderChart();
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "1D" })).toBeInTheDocument();
  });
});
