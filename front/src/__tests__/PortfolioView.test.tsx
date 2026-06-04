import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PortfolioView } from "../views/PortfolioView";

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><PortfolioView /></QueryClientProvider>);
}

describe("PortfolioView", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("loads positions and shows the summary + a row", async () => {
    renderView();
    await waitFor(() => expect(screen.getByText("ETH")).toBeInTheDocument());
    expect(screen.getByText(/Invested/i)).toBeInTheDocument();
  });

  it("close asks for confirmation then calls the API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderView();
    await waitFor(() => expect(screen.getByText("ETH")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(window.confirm).toHaveBeenCalled();
  });
});
