import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppNav } from "../components/AppNav";

describe("AppNav", () => {
  it("renders both views and fires onChange", async () => {
    const onChange = vi.fn();
    render(<AppNav value="screener" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Screener" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Portfolio" }));
    expect(onChange).toHaveBeenCalledWith("portfolio");
  });
});
