import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
}

describe("App", () => {
  it("shows category tabs and loads a page", async () => {
    renderApp();
    expect(screen.getByRole("button", { name: "Crypto" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeInTheDocument());
  });

  it("switches category on tab click", async () => {
    renderApp();
    await userEvent.click(screen.getByRole("button", { name: "Crypto" }));
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeInTheDocument());
  });
});
