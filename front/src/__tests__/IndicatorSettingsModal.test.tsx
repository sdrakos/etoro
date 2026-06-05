import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IndicatorSettingsModal } from "../components/IndicatorSettingsModal";
import type { IndicatorConfig } from "../lib/indicators";

const cfg: IndicatorConfig = { name: "RSI", calcParams: [6, 12, 24], colors: ["#aaaaaa", "#bbbbbb", "#cccccc"] };

function setup() {
  const onApply = vi.fn();
  const onReset = vi.fn();
  const onClose = vi.fn();
  render(<IndicatorSettingsModal name="RSI" config={cfg} onApply={onApply} onReset={onReset} onClose={onClose} />);
  return { onApply, onReset, onClose };
}

describe("IndicatorSettingsModal", () => {
  it("renders one number input per calcParam and applies edits", () => {
    const { onApply } = setup();
    const inputs = screen.getAllByRole("spinbutton");
    expect(inputs).toHaveLength(3);
    fireEvent.change(inputs[0], { target: { value: "9" } });
    expect(onApply).toHaveBeenLastCalledWith({ name: "RSI", calcParams: [9, 12, 24], colors: cfg.colors });
  });

  it("switches to the Style tab and edits a color", async () => {
    const { onApply } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Style" }));
    const color = screen.getByLabelText("Line 1 color");
    fireEvent.change(color, { target: { value: "#ff0000" } });
    expect(onApply).toHaveBeenLastCalledWith(
      { name: "RSI", calcParams: cfg.calcParams, colors: ["#ff0000", "#bbbbbb", "#cccccc"] });
  });

  it("fires reset and close", async () => {
    const { onReset, onClose } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Reset to defaults" }));
    expect(onReset).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalled();
  });
});
