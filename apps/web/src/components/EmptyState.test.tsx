import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "./EmptyState";

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="No cases yet" />);
    expect(screen.getByText("No cases yet")).toBeInTheDocument();
  });

  it("renders the action when given", () => {
    render(<EmptyState message="No cases yet" action={<button>New case</button>} />);
    expect(screen.getByRole("button", { name: "New case" })).toBeInTheDocument();
  });

  it("uses the design-system tokens, not the old slate/dashed classes", () => {
    render(<EmptyState message="No cases yet" />);
    const container = screen.getByText("No cases yet").closest("div[class]");
    expect(container?.className).not.toMatch(/slate|dashed/);
  });

  it("renders the illustration blob", () => {
    render(<EmptyState message="No cases yet" />);
    expect(document.querySelector("[data-testid=\"empty-state-blob\"]")).toBeInTheDocument();
  });
});
