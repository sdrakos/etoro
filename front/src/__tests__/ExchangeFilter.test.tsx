import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExchangeFilter } from "../components/ExchangeFilter";
import type { ExchangeOption } from "../types/screener";

const options: ExchangeOption[] = [
  { exchange: "Nasdaq", count: 3706 },
  { exchange: "NYSE", count: 2341 },
];

describe("ExchangeFilter", () => {
  it("renders All + options and fires onChange with the picked exchange", async () => {
    const onChange = vi.fn();
    render(<ExchangeFilter value={null} options={options} onChange={onChange} />);
    expect(screen.getByRole("option", { name: /All exchanges/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Nasdaq (3706)" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), "Nasdaq");
    expect(onChange).toHaveBeenCalledWith("Nasdaq");
  });

  it("emits null when All is selected", async () => {
    const onChange = vi.fn();
    render(<ExchangeFilter value="Nasdaq" options={options} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "__all__");
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
