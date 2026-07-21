import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrandMark } from "./BrandMark";

describe("BrandMark", () => {
  it("renders an accessible badge with the logo as its background", () => {
    render(<BrandMark />);
    const badge = screen.getByRole("img", { name: "CollaBrains" });
    expect(badge).toBeInTheDocument();
    expect(badge.style.backgroundImage).toContain("collabrains-logo");
  });

  it("sizes the badge to the size prop", () => {
    render(<BrandMark size={40} />);
    const badge = screen.getByRole("img", { name: "CollaBrains" });
    expect(badge).toHaveStyle({ width: "40px", height: "40px" });
  });
});
