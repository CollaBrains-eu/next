import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("renders every nav item as a link to the right route", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Documents" })).not.toHaveClass("text-accent");
  });

  it("renders a sliding pill element behind the nav list", () => {
    renderAt("/");
    expect(document.querySelector("[data-testid=\"nav-pill\"]")).toBeInTheDocument();
  });
});
