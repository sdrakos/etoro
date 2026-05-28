import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UniverseSelector } from "../components/UniverseSelector";
import type { Universe } from "../types/screener";

describe("UniverseSelector", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders all three buttons", () => {
    render(<UniverseSelector value="sp500" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /S&P 500/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /NASDAQ 100/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Combined/i })).toBeInTheDocument();
  });

  it("highlights the active universe", () => {
    render(<UniverseSelector value="nasdaq100" onChange={() => {}} />);
    const ndx = screen.getByRole("button", { name: /NASDAQ 100/i });
    expect(ndx).toHaveAttribute("aria-pressed", "true");
  });

  it("calls onChange with the selected universe id", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn<(u: Universe) => void>();
    render(<UniverseSelector value="sp500" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Combined/i }));
    expect(onChange).toHaveBeenCalledWith("combined");
  });
});

import { renderHook, act } from "@testing-library/react";
import { useUniverse } from "../hooks/useUniverse";

describe("useUniverse", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to sp500 when nothing stored", () => {
    const { result } = renderHook(() => useUniverse());
    expect(result.current[0]).toBe("sp500");
  });

  it("reads stored value on mount", () => {
    localStorage.setItem("etoro.screener.universe", "nasdaq100");
    const { result } = renderHook(() => useUniverse());
    expect(result.current[0]).toBe("nasdaq100");
  });

  it("writes selection to localStorage", () => {
    const { result } = renderHook(() => useUniverse());
    act(() => result.current[1]("combined"));
    expect(localStorage.getItem("etoro.screener.universe")).toBe("combined");
  });

  it("ignores invalid stored values", () => {
    localStorage.setItem("etoro.screener.universe", "garbage");
    const { result } = renderHook(() => useUniverse());
    expect(result.current[0]).toBe("sp500");
  });
});
