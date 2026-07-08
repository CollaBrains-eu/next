import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Layout from "./Layout";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

describe("Layout", () => {
  it("uses design system tokens for the page background, not raw slate classes", () => {
    const { container } = render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("bg-page");
    expect(root.className).toContain("text-ink");
    expect(root.className).not.toContain("bg-slate-50");
    expect(root.className).not.toContain("text-slate-900");
  });
});
