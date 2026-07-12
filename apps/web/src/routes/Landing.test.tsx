import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
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
  it("renders the hero heading and feature sections", () => {
    renderLanding();
    expect(screen.getByText("Organized.")).toBeInTheDocument();
    expect(screen.getByText("One platform for everything")).toBeInTheDocument();
    expect(screen.getByText("Smart documents")).toBeInTheDocument();
  });

  it("navigates to /login when the nav login button is clicked", () => {
    renderLanding();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("navigates to /login when a CTA button is clicked", () => {
    renderLanding();
    fireEvent.click(screen.getAllByRole("button", { name: /Get started/ })[0]);
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });
});
