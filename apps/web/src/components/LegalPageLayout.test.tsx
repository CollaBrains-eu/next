import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LegalPageLayout } from "./LegalPageLayout";

describe("LegalPageLayout", () => {
  it("shows the title, a placeholder notice, and each section with pending content", () => {
    render(
      <MemoryRouter>
        <LegalPageLayout title="Privacy Policy" sections={["Information we collect", "Contact us"]} />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByText("This page is a placeholder")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Information we collect" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Contact us" })).toBeInTheDocument();
    expect(screen.getAllByText("Content pending legal review.")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
  });
});
