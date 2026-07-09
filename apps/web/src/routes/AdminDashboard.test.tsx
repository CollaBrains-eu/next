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
  };
});

function goToUsersTab() {
  vi.mocked(api.getAdminStats).mockResolvedValue({
    total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
  });
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
});
