import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";
import i18n from "../lib/i18n";
import { CommandCenterStateProvider, useCommandCenterState } from "../lib/commandCenter";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listEntities: vi.fn() };
});

function OverlayProbe() {
  const { overlay } = useCommandCenterState();
  return <span data-testid="overlay-probe">{overlay}</span>;
}

function renderAt(
  path: string,
  props: { mobileOpen?: boolean; onCloseMobile?: () => void } = {},
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CommandCenterStateProvider>
        <OverlayProbe />
        <Sidebar {...props} />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    localStorage.clear();
  });

  it("renders every nav item as a link to the right route", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveClass("text-accent");
  });

  it("renders a sliding pill element behind the nav list", () => {
    renderAt("/");
    expect(document.querySelector("[data-testid=\"nav-pill\"]")).toBeInTheDocument();
  });

  it("renders an icon inside every nav link", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Dashboard" }).querySelector("svg")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cases" }).querySelector("svg")).toBeInTheDocument();
  });

  it("renders the brand mark", () => {
    renderAt("/");
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
  });

  it("renders the AlertsBell", async () => {
    renderAt("/");
    expect(await screen.findByLabelText("Alerts")).toBeInTheDocument();
  });

  it("opens the command palette when the search button is clicked", () => {
    renderAt("/");
    fireEvent.click(screen.getByLabelText("Search"));
    expect(screen.getByTestId("overlay-probe")).toHaveTextContent("palette");
  });

  it("does not render a mobile backdrop when closed", () => {
    renderAt("/");
    expect(screen.queryByTestId("sidebar-backdrop")).not.toBeInTheDocument();
  });

  it("renders a mobile backdrop and slides the drawer in when open", () => {
    renderAt("/", { mobileOpen: true });
    expect(screen.getByTestId("sidebar-backdrop")).toBeInTheDocument();
    expect(document.querySelector("aside")).toHaveClass("translate-x-0");
  });

  it("calls onCloseMobile when the backdrop is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile when a nav link is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByRole("link", { name: "Cases" }));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile on Escape when open", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  describe("collapse", () => {
    it("defaults to expanded", () => {
      renderAt("/");
      expect(document.querySelector("aside")).toHaveClass("md:w-56");
      expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeInTheDocument();
    });

    it("collapses and persists the preference when the toggle is clicked", () => {
      renderAt("/");
      fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
      expect(document.querySelector("aside")).toHaveClass("md:w-16");
      expect(localStorage.getItem("collabrains_sidebar_collapsed")).toBe("true");
      expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
    });

    it("restores a persisted collapsed state on mount", () => {
      localStorage.setItem("collabrains_sidebar_collapsed", "true");
      renderAt("/");
      expect(document.querySelector("aside")).toHaveClass("md:w-16");
    });

    it("keeps nav labels in the accessible tree (visually-hidden at desktop widths) when collapsed", () => {
      localStorage.setItem("collabrains_sidebar_collapsed", "true");
      renderAt("/");
      const dashboardLink = screen.getByRole("link", { name: "Dashboard" });
      expect(dashboardLink.querySelector("span")).toHaveClass("md:sr-only");
    });
  });

  describe("language switching", () => {
    afterEach(() => {
      i18n.changeLanguage("en");
    });

    it("renders nav labels in Dutch when the language is switched to nl", async () => {
      await i18n.changeLanguage("nl");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Zaken" })).toHaveAttribute("href", "/cases");
    });

    it("renders nav labels in German when the language is switched to de", async () => {
      await i18n.changeLanguage("de");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Fälle" })).toHaveAttribute("href", "/cases");
    });
  });
});
