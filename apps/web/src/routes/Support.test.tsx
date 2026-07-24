import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import Support from "./Support";

describe("Support", () => {
  it("shows a support email CTA and a link to the changelog", () => {
    render(
      <MemoryRouter>
        <Support />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Support" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Email info@collabrains.eu" })).toHaveAttribute(
      "href", "mailto:info@collabrains.eu",
    );
    expect(screen.getByRole("link", { name: "See what's new" })).toHaveAttribute("href", "/changelog");
  });
});
