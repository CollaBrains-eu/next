import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InvitationLanding from "./InvitationLanding";
import { AuthProvider } from "../lib/auth";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    checkInvitation: vi.fn(),
    acceptInvitation: vi.fn(),
    fetchMe: vi.fn(),
    getPreferences: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getPreferences).mockResolvedValue({ preferred_language: null, date_format: "eu", time_format: "h24" });
  vi.mocked(api.fetchMe).mockRejectedValue(new api.ApiError(401, "not logged in"));
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/invitations/:token" element={<InvitationLanding />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("InvitationLanding", () => {
  it("shows an invalid message for an unknown/expired invitation", async () => {
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: false, organization_name: null, email: null, account_exists: false,
    });
    renderAt("/invitations/bad-token");
    expect(await screen.findByRole("heading", { name: "Invitation no longer valid" })).toBeInTheDocument();
  });

  it("offers to create an account when the invitee has no account yet", async () => {
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: true, organization_name: "Acme Legal", email: "invitee@example.com", account_exists: false,
    });
    renderAt("/invitations/good-token");

    expect(await screen.findByRole("heading", { name: /Join Acme Legal/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create your account" })).toHaveAttribute(
      "href", "/register?invitation=good-token",
    );
  });

  it("offers to log in when the invitee already has an account", async () => {
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: true, organization_name: "Acme Legal", email: "invitee@example.com", account_exists: true,
    });
    renderAt("/invitations/good-token");

    expect(await screen.findByRole("link", { name: "Log in to accept" })).toHaveAttribute("href", "/login");
  });

  it("accepts the invitation directly when already logged in", async () => {
    vi.mocked(api.fetchMe).mockResolvedValue({
      username: "existing", display_name: "Existing User", email: "existing@example.com", role: "member",
      phone_number: null, phone_prompt_dismissed: true,
    });
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: true, organization_name: "Acme Legal", email: "existing@example.com", account_exists: true,
    });
    vi.mocked(api.acceptInvitation).mockResolvedValue("fresh-token");
    renderAt("/invitations/good-token");

    const acceptButton = await screen.findByRole("button", { name: "Accept invitation" });
    fireEvent.click(acceptButton);

    await waitFor(() => expect(api.acceptInvitation).toHaveBeenCalledWith("good-token"));
    await waitFor(() => expect(localStorage.getItem("collabrains_token")).toBe("fresh-token"));
  });
});
