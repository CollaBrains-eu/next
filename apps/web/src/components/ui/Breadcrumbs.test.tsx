import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { Breadcrumbs } from "./Breadcrumbs";

describe("Breadcrumbs", () => {
  it("renders every item's label", () => {
    render(
      <MemoryRouter>
        <Breadcrumbs items={[{ label: "Cases", to: "/cases" }, { label: "Case #12" }]} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Cases")).toBeInTheDocument();
    expect(screen.getByText("Case #12")).toBeInTheDocument();
  });

  it("renders a link for every item except the last", () => {
    render(
      <MemoryRouter>
        <Breadcrumbs items={[{ label: "Cases", to: "/cases" }, { label: "Case #12" }]} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.queryByRole("link", { name: "Case #12" })).not.toBeInTheDocument();
  });
});
