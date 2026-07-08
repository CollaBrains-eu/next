import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Card from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("uses the design-system surface/edge/shadow tokens instead of the old slate classes", () => {
    render(<Card>Content</Card>);
    const card = screen.getByText("Content");
    expect(card).toHaveClass("bg-surface", "border-edge", "shadow-raised");
    expect(card.className).not.toMatch(/slate/);
  });

  it("still accepts an additional className", () => {
    render(<Card className="mt-4">Content</Card>);
    expect(screen.getByText("Content")).toHaveClass("mt-4");
  });
});
