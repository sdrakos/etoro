import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChartToolbar } from "../components/ChartToolbar";

describe("ChartToolbar", () => {
  it("renders timeframes + indicators, gears for active, and fires callbacks", async () => {
    const onTimeframe = vi.fn();
    const onToggle = vi.fn();
    const onOpenSettings = vi.fn();
    render(<ChartToolbar timeframe="1d" onTimeframe={onTimeframe}
      active={new Set(["MA", "VOL"])} onToggle={onToggle} onOpenSettings={onOpenSettings} />);

    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1H" }));
    expect(onTimeframe).toHaveBeenCalledWith("1h");

    await userEvent.click(screen.getByRole("button", { name: "RSI" }));   // inactive → toggle only
    expect(onToggle).toHaveBeenCalledWith("RSI");

    // active indicators expose a settings gear; inactive ones don't
    expect(screen.queryByRole("button", { name: "RSI settings" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "MA settings" }));
    expect(onOpenSettings).toHaveBeenCalledWith("MA");
  });
});
