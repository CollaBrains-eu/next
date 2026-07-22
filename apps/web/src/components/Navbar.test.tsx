import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Navbar from "./Navbar";
import i18n from "../lib/i18n";
import { CommandCenterStateProvider, useCommandCenterState } from "../lib/commandCenter";
import * as api from "../lib/api";
import * as auth from "../lib/auth";

vi.mock("../lib/auth", async () => {
  const actual = await vi.importActual<typeof auth>("../lib/auth");
  return { ...actual, useAuth: vi.fn() };
});

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, getPendingReviewEntityCount: vi.fn() };
});

function OverlayProbe() {
  const { overlay } = useCommandCenterState();
  return <span data-testid="overlay-probe">{overlay}</span>;
}

function mockUser(role?: string) {
  vi.mocked(auth.useAuth).mockReturnValue({
    user: { display_name: "Ada Admin", role } as never,
    logout: vi.fn(),
  } as never);
}

// MobileNavDrawer stays mounted (just CSS-translated off-screen) even when
// closed, so its full item list -- including ones the desktop bar only
// shows behind "More" -- is simultaneously present in jsdom, which doesn't
// evaluate the responsive CSS that keeps only one visible per breakpoint.
// Scope queries to the desktop primary-nav container to avoid ambiguity.
function primaryNav() {
  return within(screen.getByTestId("navbar-primary-nav"));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CommandCenterStateProvider>
        <OverlayProbe />
        <Navbar />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("Navbar", () => {
  beforeEach(() => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 0 });
    mockUser("member");
  });

  it("renders the brand mark linking to the root route", () => {
    renderAt("/");
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /CollaBrains|Collabr/ })[0]).toHaveAttribute("href", "/");
  });

  it("renders every primary nav item as a link to the right route", () => {
    renderAt("/");
    const nav = primaryNav();
    expect(nav.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(nav.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
    expect(nav.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(nav.getByRole("link", { name: "Tasks" })).toHaveAttribute("href", "/tasks");
    expect(nav.getByRole("link", { name: "AI Chat" })).toHaveAttribute("href", "/chat");
  });

  it("does not render settings as a top-level nav item", () => {
    renderAt("/");
    expect(primaryNav().queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("marks the primary item matching the current route as active", () => {
    renderAt("/cases");
    const nav = primaryNav();
    expect(nav.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(nav.getByRole("link", { name: "Dashboard" })).not.toHaveClass("text-accent");
  });

  it("puts secondary items behind the More dropdown and navigates on selection", () => {
    renderAt("/");
    expect(primaryNav().queryByRole("link", { name: "Vehicles" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("More"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Vehicles" }));
    expect(screen.getByTestId("mobile-header-title")).toHaveTextContent("Vehicles");
  });

  it("renders the AlertsBell", async () => {
    renderAt("/");
    expect((await screen.findAllByLabelText("Alerts")).length).toBeGreaterThan(0);
  });

  it("opens the command palette when a search button is clicked", () => {
    renderAt("/");
    fireEvent.click(screen.getAllByLabelText("Search")[0]);
    expect(screen.getByTestId("overlay-probe")).toHaveTextContent("palette");
  });

  it("shows the account dropdown with Settings and Sign out, but not Admin, for a non-admin", () => {
    renderAt("/");
    // The desktop account-dropdown trigger's Avatar renders before the mobile
    // header's profile-link Avatar in DOM order -- [0] is the dropdown one.
    fireEvent.click(screen.getAllByText("AA")[0]);
    expect(screen.getByRole("menuitem", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Admin" })).not.toBeInTheDocument();
  });

  it("shows Admin in the account dropdown for an admin", () => {
    mockUser("admin");
    renderAt("/");
    fireEvent.click(screen.getAllByText("AA")[0]);
    expect(screen.getByRole("menuitem", { name: "Admin" })).toBeInTheDocument();
  });

  it("shows a mobile header with the profile avatar linking to settings and the current section title", () => {
    renderAt("/documents");
    const link = screen.getByLabelText("My profile");
    expect(link).toHaveAttribute("href", "/settings");
    expect(screen.getByTestId("mobile-header-title")).toHaveTextContent("Documents");
  });

  it("opens the mobile nav drawer when the hamburger is clicked", () => {
    renderAt("/");
    expect(screen.queryByTestId("mobile-nav-backdrop")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Open menu"));
    expect(screen.getByTestId("mobile-nav-backdrop")).toBeInTheDocument();
  });

  it("toggles dark mode when the sun/moon button is clicked", () => {
    renderAt("/");
    const toggle = screen.getAllByLabelText("🌙 Dark mode")[0];
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    fireEvent.click(screen.getAllByLabelText("☀️ Light mode")[0]);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  describe("language switching", () => {
    afterEach(() => {
      i18n.changeLanguage("en");
    });

    it("renders nav labels in Dutch when the language is switched to nl", async () => {
      await i18n.changeLanguage("nl");
      renderAt("/");
      const nav = primaryNav();
      expect(nav.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(nav.getByRole("link", { name: "Zaken" })).toHaveAttribute("href", "/cases");
    });

    it("renders nav labels in German when the language is switched to de", async () => {
      await i18n.changeLanguage("de");
      renderAt("/");
      const nav = primaryNav();
      expect(nav.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(nav.getByRole("link", { name: "Fälle" })).toHaveAttribute("href", "/cases");
    });
  });
});
