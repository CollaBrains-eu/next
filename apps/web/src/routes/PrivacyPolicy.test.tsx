import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import PrivacyPolicy from "./PrivacyPolicy";
import TermsOfService from "./TermsOfService";
import CookiePolicy from "./CookiePolicy";

describe("Legal document pages", () => {
  it("renders the Privacy Policy page with its sections", () => {
    render(
      <MemoryRouter>
        <PrivacyPolicy />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your rights" })).toBeInTheDocument();
  });

  it("renders the Terms of Service page with its sections", () => {
    render(
      <MemoryRouter>
        <TermsOfService />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: "Terms of Service" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Subscriptions and billing" })).toBeInTheDocument();
  });

  it("renders the Cookie Policy page with its sections", () => {
    render(
      <MemoryRouter>
        <CookiePolicy />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: "Cookie Policy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Managing your preferences" })).toBeInTheDocument();
  });
});
