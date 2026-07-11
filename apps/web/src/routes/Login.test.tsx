import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";
import { ApiError } from "../lib/api";

const mockLogin = vi.fn();
let mockUser: { display_name: string } | null = null;

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: mockUser, login: mockLogin }),
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<div>Dashboard page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Login", () => {
  beforeEach(() => {
    mockUser = null;
    mockLogin.mockReset();
  });

  it("renders the sign-in form", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("submits the entered credentials and navigates on success", async () => {
    mockLogin.mockResolvedValue(undefined);
    renderLogin();

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "hunter2" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith("alice", "hunter2"));
    await waitFor(() => expect(screen.getByText("Dashboard page")).toBeInTheDocument());
  });

  it("shows an error message when login fails", async () => {
    mockLogin.mockRejectedValue(new ApiError(401, "Invalid credentials"));
    renderLogin();

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
  });

  it("redirects away when already logged in", () => {
    mockUser = { display_name: "Ada" };
    renderLogin();
    expect(screen.getByText("Dashboard page")).toBeInTheDocument();
  });
});
