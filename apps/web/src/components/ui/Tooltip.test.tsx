import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tooltip } from "./Tooltip";

describe("Tooltip", () => {
  it("renders the child content", () => {
    render(
      <Tooltip label="Owner-only action">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(screen.getByRole("button", { name: "Hover me" })).toBeInTheDocument();
  });

  it("renders the label text in the DOM (visibility is CSS-only, not asserted here)", () => {
    render(
      <Tooltip label="Owner-only action">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(screen.getByText("Owner-only action")).toBeInTheDocument();
  });

  it("merges an optional className onto the wrapper without dropping the default classes", () => {
    render(
      <Tooltip label="Owner-only action" className="w-full">
        <button>Hover me</button>
      </Tooltip>
    );
    const wrapper = screen.getByRole("button", { name: "Hover me" }).parentElement;
    expect(wrapper).toHaveClass("group", "relative", "inline-flex", "w-full");
  });
});
