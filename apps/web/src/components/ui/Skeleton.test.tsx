import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Skeleton, SkeletonLines } from "./Skeleton";

describe("Skeleton", () => {
  it("applies the given className to the root element", () => {
    const { container } = render(<Skeleton className="h-4 w-20" />);
    expect(container.firstChild).toHaveClass("h-4", "w-20");
  });
});

describe("SkeletonLines", () => {
  it("renders three shimmer bars", () => {
    render(<SkeletonLines />);
    expect(screen.getByTestId("skeleton-lines").children).toHaveLength(3);
  });
});
