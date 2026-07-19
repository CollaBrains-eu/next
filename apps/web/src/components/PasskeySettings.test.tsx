import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PasskeySettings } from "./PasskeySettings";
import * as api from "../lib/api";
import * as webauthnLib from "../lib/webauthn";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listWebauthnCredentials: vi.fn(),
    deleteWebauthnCredential: vi.fn(),
  };
});

vi.mock("../lib/webauthn", async () => {
  const actual = await vi.importActual<typeof webauthnLib>("../lib/webauthn");
  return {
    ...actual,
    isPasskeySupported: vi.fn(),
    registerPasskey: vi.fn(),
  };
});

describe("PasskeySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(webauthnLib.isPasskeySupported).mockReturnValue(true);
    vi.mocked(api.listWebauthnCredentials).mockResolvedValue([]);
    vi.spyOn(window, "prompt").mockReturnValue("My Device");
  });

  it("loads and lists existing passkeys", async () => {
    vi.mocked(api.listWebauthnCredentials).mockResolvedValue([
      { id: "c1", label: "MacBook", created_at: "2026-01-01T00:00:00Z", last_used_at: null },
    ]);
    render(<PasskeySettings />);
    expect(await screen.findByText("MacBook")).toBeInTheDocument();
  });

  it("shows a specific message when the device already has a passkey registered for this account", async () => {
    vi.mocked(webauthnLib.registerPasskey).mockRejectedValue(new DOMException("dup", "InvalidStateError"));
    render(<PasskeySettings />);
    await screen.findByText("No passkeys registered yet.");

    fireEvent.click(screen.getByRole("button", { name: "Add passkey" }));

    expect(
      await screen.findByText("This device already has a passkey registered for your account.")
    ).toBeInTheDocument();
  });

  it("shows the generic error message for other registration failures", async () => {
    vi.mocked(webauthnLib.registerPasskey).mockRejectedValue(new Error("NotAllowedError"));
    render(<PasskeySettings />);
    await screen.findByText("No passkeys registered yet.");

    fireEvent.click(screen.getByRole("button", { name: "Add passkey" }));

    expect(await screen.findByText("Failed to register passkey")).toBeInTheDocument();
  });

  it("shows the server's own message when the API rejects the request", async () => {
    vi.mocked(webauthnLib.registerPasskey).mockRejectedValue(
      new api.ApiError(400, "Registration challenge expired, try again")
    );
    render(<PasskeySettings />);
    await screen.findByText("No passkeys registered yet.");

    fireEvent.click(screen.getByRole("button", { name: "Add passkey" }));

    expect(await screen.findByText("Registration challenge expired, try again")).toBeInTheDocument();
  });

  it("reloads the credential list after a successful registration", async () => {
    vi.mocked(webauthnLib.registerPasskey).mockResolvedValue(undefined);
    vi.mocked(api.listWebauthnCredentials)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        { id: "c1", label: "My Device", created_at: "2026-01-01T00:00:00Z", last_used_at: null },
      ]);
    render(<PasskeySettings />);
    await screen.findByText("No passkeys registered yet.");

    fireEvent.click(screen.getByRole("button", { name: "Add passkey" }));

    expect(await screen.findByText("My Device")).toBeInTheDocument();
    expect(webauthnLib.registerPasskey).toHaveBeenCalledWith("My Device");
  });
});
