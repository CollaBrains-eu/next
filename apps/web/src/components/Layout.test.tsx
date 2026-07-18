import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import Layout from "./Layout";
import { CommandCenterStateProvider } from "../lib/commandCenter";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin", role: "user" }, logout: vi.fn() }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, getPendingReviewEntityCount: vi.fn() };
});

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
  beforeEach(() => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 0 });
  });

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

  it("shows the CollaBrains brand name on the root route", () => {
    renderLayout();
    expect(screen.getByTestId("mobile-header-title")).toHaveTextContent("CollaBrains");
  });

  it("shows a bottom tab bar with the primary mobile destinations", () => {
    renderLayout();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
    expect(screen.getByText("Dossiers")).toBeInTheDocument();
    expect(screen.getByText("Acties")).toBeInTheDocument();
  });

  it("shows a profile avatar linking to settings", () => {
    renderLayout();
    const link = screen.getByLabelText("My profile");
    expect(link).toHaveAttribute("href", "/settings");
    expect(link.textContent).toContain("AA");
  });

  it("toggles dark mode when the sun/moon button is clicked", () => {
    renderLayout();
    const toggle = screen.getByLabelText("🌙 Dark mode");
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    fireEvent.click(screen.getByLabelText("☀️ Light mode"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
