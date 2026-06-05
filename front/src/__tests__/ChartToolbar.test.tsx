import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChartToolbar } from "../components/ChartToolbar";

describe("ChartToolbar", () => {
  it("renders timeframes + indicators and fires callbacks", async () => {
    const onTimeframe = vi.fn();
    const onToggle = vi.fn();
    render(<ChartToolbar timeframe="1d" onTimeframe={onTimeframe}
                         active={new Set(["MA", "VOL"])} onToggle={onToggle} />);
    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1H" }));
    expect(onTimeframe).toHaveBeenCalledWith("1h");
    await userEvent.click(screen.getByRole("button", { name: "RSI" }));
    expect(onToggle).toHaveBeenCalledWith("RSI");
  });
});
