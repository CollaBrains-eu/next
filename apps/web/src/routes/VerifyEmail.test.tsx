import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VerifyEmail from "./VerifyEmail";
import { AuthProvider } from "../lib/auth";
import * as api from "../lib/api";

function SettingsStub() {
  const [searchParams] = useSearchParams();
  return <div>Settings page (checkout={searchParams.get("checkout") ?? "none"})</div>;
}

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, verifyEmail: vi.fn(), fetchMe: vi.fn(), getPreferences: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(api.getPreferences).mockResolvedValue({ preferred_language: null, date_format: "eu", time_format: "h24" });
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/settings" element={<SettingsStub />} />
          <Route path="/" element={<div>Home page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("VerifyEmail", () => {
  it("verifies the token, logs in, and stores the access token", async () => {
    vi.mocked(api.verifyEmail).mockResolvedValue("fresh-access-token");
    vi.mocked(api.fetchMe).mockResolvedValue({
      username: "ada", display_name: "Ada", email: "ada@example.com", role: "member",
      phone_number: null, phone_prompt_dismissed: true,
    });
    renderAt("/verify-email?token=good-token");

    await waitFor(() => expect(api.verifyEmail).toHaveBeenCalledWith("good-token"));
    await waitFor(() => expect(localStorage.getItem("collabrains_token")).toBe("fresh-access-token"));
    expect(await screen.findByText("Home page")).toBeInTheDocument();
  });

  it("redirects to Settings with the remembered plan when one was chosen on Landing", async () => {
    window.localStorage.setItem("collabrains_pending_plan", "pro");
    vi.mocked(api.verifyEmail).mockResolvedValue("fresh-access-token");
    vi.mocked(api.fetchMe).mockResolvedValue({
      username: "ada", display_name: "Ada", email: "ada@example.com", role: "member",
      phone_number: null, phone_prompt_dismissed: true,
    });
    renderAt("/verify-email?token=good-token");

    expect(await screen.findByText("Settings page (checkout=pro)")).toBeInTheDocument();
    expect(window.localStorage.getItem("collabrains_pending_plan")).toBeNull();
  });

  it("shows an error message when the token is invalid", async () => {
    vi.mocked(api.verifyEmail).mockRejectedValue(new api.ApiError(400, "invalid"));
    renderAt("/verify-email?token=bad-token");
    expect(await screen.findByRole("heading", { name: "Link no longer valid" })).toBeInTheDocument();
  });

  it("shows an error message when there is no token in the URL", async () => {
    renderAt("/verify-email");
    await waitFor(() => expect(api.verifyEmail).not.toHaveBeenCalled());
    expect(await screen.findByRole("heading", { name: "Link no longer valid" })).toBeInTheDocument();
  });
});
