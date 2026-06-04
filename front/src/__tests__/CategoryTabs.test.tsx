import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CategoryTabs } from "../components/CategoryTabs";

describe("CategoryTabs", () => {
  it("renders all six categories and fires onChange", async () => {
    const onChange = vi.fn();
    render(<CategoryTabs value="stocks" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Stocks" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crypto" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Crypto" }));
    expect(onChange).toHaveBeenCalledWith("crypto");
  });
});
