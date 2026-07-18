import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminDashboard from "./AdminDashboard";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getAdminStats: vi.fn(),
    getAdminAiUsage: vi.fn(),
    getAdminHealth: vi.fn(),
    listBugReports: vi.fn(),
    createAdminUser: vi.fn(),
    setUserRole: vi.fn(),
    resetUserPassword: vi.fn(),
    deactivateUser: vi.fn(),
    setUserPhone: vi.fn(),
    listAdminUsers: vi.fn(),
  };
});

function goToUsersTab() {
  vi.mocked(api.getAdminStats).mockResolvedValue({
    total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
  });
  vi.mocked(api.listAdminUsers).mockResolvedValue([]);
  render(<AdminDashboard />);
  fireEvent.click(screen.getByRole("button", { name: "Users" }));
}

describe("AdminDashboard Users tab", () => {
  it("opens the add-user form when 'Add user' is clicked", () => {
    goToUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "+ Add user" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Add user")).toBeInTheDocument();
  });

  it("submits the form and shows the one-time temporary password", async () => {
    vi.mocked(api.createAdminUser).mockResolvedValue({
      username: "newperson",
      temporary_password: "a-temp-pw-123",
    });
    goToUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "+ Add user" }));

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "newperson" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New Person" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@collabrains.eu" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() =>
      expect(api.createAdminUser).toHaveBeenCalledWith({
        username: "newperson",
        display_name: "New Person",
        email: "new@collabrains.eu",
        is_admin: false,
        phone_number: null,
      }),
    );

    expect(await screen.findByTestId("temp-password")).toHaveTextContent("a-temp-pw-123");
    // The form modal closes after a successful create.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error and keeps the form open when creation fails", async () => {
    vi.mocked(api.createAdminUser).mockRejectedValue(
      new api.ApiError(409, "Username already exists"),
    );
    goToUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "+ Add user" }));

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "existing" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Existing Person" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "e@collabrains.eu" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    expect(await screen.findByText("Username already exists")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("dismisses the temporary-password card", async () => {
    vi.mocked(api.createAdminUser).mockResolvedValue({
      username: "newperson",
      temporary_password: "a-temp-pw-123",
    });
    goToUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "+ Add user" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "newperson" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New Person" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@collabrains.eu" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    await screen.findByTestId("temp-password");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByTestId("temp-password")).not.toBeInTheDocument();
  });

  it("submits the phone number when one is entered", async () => {
    vi.mocked(api.createAdminUser).mockResolvedValue({
      username: "newperson", temporary_password: "a-temp-pw-123",
    });
    goToUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "+ Add user" }));

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "newperson" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New Person" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@collabrains.eu" } });
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+491511234567" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() =>
      expect(api.createAdminUser).toHaveBeenCalledWith(
        expect.objectContaining({ phone_number: "+491511234567" }),
      ),
    );
  });

  it("lists existing users", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "alice", display_name: "Alice", email: "alice@collabrains.eu",
        role: "member", phone_number: "+15551230001", created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("+15551230001")).toBeInTheDocument();
  });

  it("shows a load-more button when a full page comes back, and loads the next page", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    const fullPage = Array.from({ length: 50 }, (_, i) => ({
      id: `u${i}`, username: `user${i}`, display_name: `User ${i}`, email: null,
      role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      is_active: true,
    }));
    vi.mocked(api.listAdminUsers)
      .mockResolvedValueOnce(fullPage)
      .mockResolvedValueOnce([
        {
          id: "u50", username: "user50", display_name: "User 50", email: null,
          role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
          is_active: true,
        },
      ]);
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    const loadMore = await screen.findByRole("button", { name: "Load more" });
    fireEvent.click(loadMore);

    expect(await screen.findByText("user50")).toBeInTheDocument();
    await waitFor(() => expect(api.listAdminUsers).toHaveBeenCalledWith(50, 50));
  });

  it("changes a member's role to admin via the row action menu", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserRole).mockResolvedValue({
      id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
      role: "admin", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      is_active: true,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Make admin" }));

    await waitFor(() => expect(api.setUserRole).toHaveBeenCalledWith("u1", "admin"));
  });

  it("shows an inline error when role change fails", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserRole).mockRejectedValue(new api.ApiError(500, "boom"));
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Make admin" }));

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("sets a user's phone number via the row action menu", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserPhone).mockResolvedValue({
      id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
      role: "member", phone_number: "+15551239999", created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      is_active: true,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Set phone" }));

    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+15551239999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.setUserPhone).toHaveBeenCalledWith("u1", "+15551239999"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error inside the phone modal when the save fails", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserPhone).mockRejectedValue(new api.ApiError(409, "Already linked"));
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Set phone" }));
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+15551239999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Already linked")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

});
