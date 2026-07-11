import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Layout from "./Layout";
import { CommandCenterStateProvider } from "../lib/commandCenter";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

function renderLayout() {
  return render(
    <MemoryRouter>
      <CommandCenterStateProvider>
        <Layout>
          <div>content</div>
        </Layout>
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("Layout", () => {
  it("uses design system tokens for the page background, not raw slate classes", () => {
    const { container } = renderLayout();
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("bg-page");
    expect(root.className).toContain("text-ink");
    expect(root.className).not.toContain("bg-slate-50");
    expect(root.className).not.toContain("text-slate-900");
  });

  it("does not show the mobile sidebar backdrop until the hamburger is clicked", () => {
    renderLayout();
    expect(screen.queryByTestId("sidebar-backdrop")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByTestId("sidebar-backdrop")).toBeInTheDocument();
  });

  it("closes the mobile sidebar when its backdrop is clicked", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    fireEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(screen.queryByTestId("sidebar-backdrop")).not.toBeInTheDocument();
  });
});
