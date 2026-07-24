import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Onboard from "./Onboard";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, checkOnboardingToken: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Onboard />
    </MemoryRouter>
  );
}

describe("Onboard", () => {
  it("shows a welcome message with the user's name for a valid token", async () => {
    vi.mocked(api.checkOnboardingToken).mockResolvedValue({
      valid: true, user_id: "u1", display_name: "Marlinde Hordijk",
    });
    renderAt("/onboard?token=good-token");
    expect(await screen.findByRole("heading", { name: /Welcome, Marlinde Hordijk/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue to sign in" })).toHaveAttribute("href", "/login");
  });

  it("shows an invalid-link message when the token is not valid", async () => {
    vi.mocked(api.checkOnboardingToken).mockResolvedValue({ valid: false, user_id: null, display_name: null });
    renderAt("/onboard?token=expired-token");
    expect(await screen.findByRole("heading", { name: "Link no longer valid" })).toBeInTheDocument();
  });

  it("shows an invalid-link message when there is no token in the URL", async () => {
    renderAt("/onboard");
    await waitFor(() => expect(api.checkOnboardingToken).not.toHaveBeenCalled());
    expect(await screen.findByRole("heading", { name: "Link no longer valid" })).toBeInTheDocument();
  });

  it("shows an invalid-link message when the API call fails", async () => {
    vi.mocked(api.checkOnboardingToken).mockRejectedValue(new Error("network error"));
    renderAt("/onboard?token=whatever");
    expect(await screen.findByRole("heading", { name: "Link no longer valid" })).toBeInTheDocument();
  });
});
