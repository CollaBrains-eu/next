import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SplitView } from "./SplitView";

describe("SplitView", () => {
  it("renders only the list when disabled", () => {
    render(<SplitView enabled={false} list={<p>The list</p>} detail={<p>The detail</p>} />);
    expect(screen.getByText("The list")).toBeInTheDocument();
    expect(screen.queryByText("The detail")).not.toBeInTheDocument();
  });

  it("renders list and detail side by side when enabled", () => {
    render(<SplitView enabled list={<p>The list</p>} detail={<p>The detail</p>} />);
    expect(screen.getByText("The list")).toBeInTheDocument();
    expect(screen.getByText("The detail")).toBeInTheDocument();
  });

  it("shows a placeholder message when enabled but detail is null", () => {
    render(<SplitView enabled list={<p>The list</p>} detail={null} />);
    expect(screen.getByText(/select an item to preview it here/i)).toBeInTheDocument();
  });

  it("does not show the placeholder when disabled, even with a null detail", () => {
    render(<SplitView enabled={false} list={<p>The list</p>} detail={null} />);
    expect(screen.queryByText(/select an item to preview it here/i)).not.toBeInTheDocument();
  });
});
