import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Register from "./Register";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, registerAccount: vi.fn(), checkInvitation: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Register />
    </MemoryRouter>
  );
}

async function fillAndSubmit(overrides: { organizationName?: string } = {}) {
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Ada Lovelace" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ada" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-horse-battery" } });
  if (overrides.organizationName !== undefined) {
    fireEvent.change(screen.getByLabelText("Organization name"), { target: { value: overrides.organizationName } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
}

describe("Register", () => {
  it("submits the form and shows a check-your-email confirmation", async () => {
    vi.mocked(api.registerAccount).mockResolvedValue({ email_sent: true });
    renderAt("/register");

    await fillAndSubmit({ organizationName: "Acme Legal" });

    await waitFor(() =>
      expect(api.registerAccount).toHaveBeenCalledWith({
        username: "ada",
        displayName: "Ada Lovelace",
        email: "ada@example.com",
        password: "correct-horse-battery",
        organizationName: "Acme Legal",
        invitationToken: undefined,
      }),
    );
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText(/ada@example.com/)).toBeInTheDocument();
  });

  it("shows a different message when the verification email could not be sent", async () => {
    vi.mocked(api.registerAccount).mockResolvedValue({ email_sent: false });
    renderAt("/register");

    await fillAndSubmit();

    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText(/verification email could not be sent/)).toBeInTheDocument();
  });

  it("shows an error message when registration fails", async () => {
    vi.mocked(api.registerAccount).mockRejectedValue(new api.ApiError(409, "This username is already taken"));
    renderAt("/register");

    await fillAndSubmit();

    expect(await screen.findByText("This username is already taken")).toBeInTheDocument();
  });

  it("pre-fills the org name and email from a valid invitation, and hides the org-name field", async () => {
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: true, organization_name: "Acme Legal", email: "invitee@example.com", account_exists: false,
    });
    renderAt("/register?invitation=inv-token");

    expect(await screen.findByText(/Join Acme Legal/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Email")).toHaveValue("invitee@example.com"));
    expect(screen.queryByLabelText("Organization name")).not.toBeInTheDocument();
  });

  it("passes the invitation token through to registerAccount", async () => {
    vi.mocked(api.checkInvitation).mockResolvedValue({
      valid: true, organization_name: "Acme Legal", email: "invitee@example.com", account_exists: false,
    });
    vi.mocked(api.registerAccount).mockResolvedValue({ email_sent: true });
    renderAt("/register?invitation=inv-token");

    await screen.findByText(/Join Acme Legal/);
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Invitee Person" } });
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "invitee" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-horse-battery" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(api.registerAccount).toHaveBeenCalledWith(
        expect.objectContaining({ invitationToken: "inv-token", email: "invitee@example.com" }),
      ),
    );
  });
});
