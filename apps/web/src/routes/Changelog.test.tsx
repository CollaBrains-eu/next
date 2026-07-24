import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import Changelog from "./Changelog";

describe("Changelog", () => {
  it("lists the recent release entries", () => {
    render(
      <MemoryRouter>
        <Changelog />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Changelog" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Self-service signup, team invitations, and subscription billing" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "CI/CD, automated testing, and error tracking" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Security and accessibility hardening" })).toBeInTheDocument();
  });
});
