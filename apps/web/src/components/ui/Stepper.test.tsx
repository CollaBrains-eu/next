import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Stepper } from "./Stepper";

describe("Stepper", () => {
  const steps = [{ label: "Upload" }, { label: "Review" }, { label: "Confirm" }];

  it("renders every step label", () => {
    render(<Stepper steps={steps} currentIndex={1} />);
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });

  it("renders a checkmark for completed steps, not a number", () => {
    render(<Stepper steps={steps} currentIndex={2} />);
    // Step 0 and 1 are complete (before currentIndex 2) -- only step 2's "3" should render as text.
    expect(screen.queryByText("1")).not.toBeInTheDocument();
    expect(screen.queryByText("2")).not.toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
