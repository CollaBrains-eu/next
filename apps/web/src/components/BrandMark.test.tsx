import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrandMark } from "./BrandMark";

describe("BrandMark", () => {
  it("renders an accessible svg mark", () => {
    render(<BrandMark />);
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
  });

  it("gives each instance a unique gradient id so multiple marks on one page don't collide", () => {
    render(
      <>
        <BrandMark />
        <BrandMark />
      </>
    );
    const gradientIds = Array.from(document.querySelectorAll("linearGradient")).map((el) => el.id);
    expect(gradientIds).toHaveLength(2);
    expect(new Set(gradientIds).size).toBe(2);
  });
});
