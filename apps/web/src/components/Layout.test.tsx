import { render, screen } from "@testing-library/react";
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

  it("renders the children passed to it", () => {
    renderLayout();
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("renders the Navbar and the bottom MobileTabBar", () => {
    renderLayout();
    // Navbar and MobileTabBar behavior (nav items, drawer, dark mode, etc.)
    // is covered by their own test files -- this just confirms Layout wires
    // both of them in, since that's Layout's own remaining responsibility.
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
  });
});
