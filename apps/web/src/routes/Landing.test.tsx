import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../lib/i18n";
import Landing from "./Landing";

function renderLanding() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Landing", () => {
  beforeEach(() => {
    // The IP geolocation lookup must never make a real network call in tests --
    // reject it so Landing falls back to its synchronous browser-language guess.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network disabled in tests")));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    i18n.changeLanguage("en");
  });

  it("renders the hero heading and feature sections", () => {
    renderLanding();
    expect(screen.getByText("Organized.")).toBeInTheDocument();
    expect(screen.getByText("One platform for everything")).toBeInTheDocument();
    expect(screen.getByText("Smart documents")).toBeInTheDocument();
  });

  it("renders the premium features, pricing plans, and enterprise section", () => {
    renderLanding();
    expect(screen.getByText("Get more out of CollaBrains")).toBeInTheDocument();
    expect(screen.getByText("Email integration")).toBeInTheDocument();
    expect(screen.getByText("Simple, transparent pricing")).toBeInTheDocument();
    expect(screen.getByText("Early users")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("Free for life")).toBeInTheDocument();
    expect(screen.getByText("Business & Enterprise")).toBeInTheDocument();
    expect(screen.getByText("Your own server / on-premise installation")).toBeInTheDocument();
  });

  it("navigates to /login when the nav login button is clicked", () => {
    renderLanding();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("navigates to /login when a CTA button is clicked", () => {
    renderLanding();
    fireEvent.click(screen.getAllByRole("button", { name: "Get started" })[0]);
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("navigates to /login when the enterprise contact link is clicked", () => {
    renderLanding();
    const link = screen.getByRole("link", { name: /Contact us/ });
    expect(link).toHaveAttribute("href", "mailto:info@collabrains.eu");
  });

  it("switches the UI language via the globe switcher next to login", () => {
    renderLanding();
    fireEvent.click(screen.getByRole("button", { name: "Change language" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Nederlands" }));
    expect(screen.getByRole("button", { name: "Inloggen" })).toBeInTheDocument();
  });
});
