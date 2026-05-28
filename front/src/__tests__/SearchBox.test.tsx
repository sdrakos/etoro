import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchBox } from "../components/SearchBox";

describe("SearchBox", () => {
  it("renders with placeholder", () => {
    render(<SearchBox onSearch={() => {}} />);
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("calls onSearch (debounced) after typing", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onSearch = vi.fn();
    render(<SearchBox onSearch={onSearch} debounceMs={200} />);
    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "NVDA");
    expect(onSearch).not.toHaveBeenCalled();
    vi.advanceTimersByTime(250);
    expect(onSearch).toHaveBeenCalledWith("NVDA");
    vi.useRealTimers();
  });

  it("clear button empties input and fires onSearch('')", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<SearchBox onSearch={onSearch} debounceMs={0} />);
    const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
    await user.type(input, "AAPL");
    await user.click(screen.getByRole("button", { name: /clear/i }));
    expect(input.value).toBe("");
    expect(onSearch).toHaveBeenLastCalledWith("");
  });
});
