import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { MobileNavDrawer } from "./MobileNavDrawer";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

function renderAt(path: string, open: boolean, onClose = vi.fn()) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MobileNavDrawer open={open} onClose={onClose} />
    </MemoryRouter>
  );
}

describe("MobileNavDrawer", () => {
  it("does not render a backdrop when closed", () => {
    renderAt("/", false);
    expect(screen.queryByTestId("mobile-nav-backdrop")).not.toBeInTheDocument();
  });

  it("renders every nav item as a link, plus sign out, when open", () => {
    renderAt("/", true);
    expect(screen.getByTestId("mobile-nav-backdrop")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("Sign out")).toBeInTheDocument();
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases", true);
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveClass("text-accent");
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    renderAt("/", true, onClose);
    fireEvent.click(screen.getByTestId("mobile-nav-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when a nav link is clicked", () => {
    const onClose = vi.fn();
    renderAt("/", true, onClose);
    fireEvent.click(screen.getByRole("link", { name: "Cases" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on Escape when open", () => {
    const onClose = vi.fn();
    renderAt("/", true, onClose);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
