import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceSharing } from "./WorkspaceSharing";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listMyWorkspaceMembers: vi.fn(),
    listMyWorkspaceInvitations: vi.fn(),
    listWorkspacesSharedWithMe: vi.fn(),
    lookupUserByPhone: vi.fn(),
    inviteWorkspaceMember: vi.fn(),
    revokeWorkspaceMember: vi.fn(),
    updateWorkspaceMemberExport: vi.fn(),
    acceptWorkspaceInvitation: vi.fn(),
    declineWorkspaceInvitation: vi.fn(),
  };
});

function member(overrides: Partial<api.WorkspaceMemberOut> = {}): api.WorkspaceMemberOut {
  return {
    id: "wm-1",
    owner_id: "owner-1",
    owner_username: "owner1",
    owner_display_name: "Owner One",
    member_id: "member-1",
    member_username: "member1",
    member_display_name: "Member One",
    can_export: false,
    status: "accepted",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("WorkspaceSharing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listMyWorkspaceMembers).mockResolvedValue([]);
    vi.mocked(api.listMyWorkspaceInvitations).mockResolvedValue([]);
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([]);
  });

  it("shows an empty state when nothing is shared", async () => {
    render(<WorkspaceSharing />);
    expect(await screen.findByText("You haven't shared your workspace with anyone yet.")).toBeInTheDocument();
  });

  it("lists an accepted member with an export toggle and a remove button", async () => {
    vi.mocked(api.listMyWorkspaceMembers).mockResolvedValue([member()]);
    render(<WorkspaceSharing />);
    expect(await screen.findByText("Member One")).toBeInTheDocument();
    expect(screen.getByText("Allow export")).toBeInTheDocument();
  });

  it("looks up a phone number and invites the found user", async () => {
    vi.mocked(api.lookupUserByPhone).mockResolvedValue({
      id: "found-1", username: "foundu", display_name: "Found User",
    });
    vi.mocked(api.inviteWorkspaceMember).mockResolvedValue(member({ member_id: "found-1" }));
    render(<WorkspaceSharing />);
    await screen.findByText("You haven't shared your workspace with anyone yet.");

    fireEvent.change(screen.getByPlaceholderText("Phone number, e.g. +491511234567"), {
      target: { value: "+31600000000" },
    });
    fireEvent.click(screen.getByText("Look up"));

    expect(await screen.findByText("Found User")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Invite"));

    await waitFor(() => expect(api.inviteWorkspaceMember).toHaveBeenCalledWith("found-1", false));
  });

  it("shows an error when the phone number isn't found", async () => {
    vi.mocked(api.lookupUserByPhone).mockResolvedValue(null);
    render(<WorkspaceSharing />);
    await screen.findByText("You haven't shared your workspace with anyone yet.");

    fireEvent.change(screen.getByPlaceholderText("Phone number, e.g. +491511234567"), {
      target: { value: "+31600000001" },
    });
    fireEvent.click(screen.getByText("Look up"));

    expect(await screen.findByText("No user found with that phone number.")).toBeInTheDocument();
  });

  it("hides the invite form and shows a capacity message at 2 active members", async () => {
    vi.mocked(api.listMyWorkspaceMembers).mockResolvedValue([
      member({ id: "wm-1", member_id: "m1", member_display_name: "One" }),
      member({ id: "wm-2", member_id: "m2", member_display_name: "Two", status: "pending" }),
    ]);
    render(<WorkspaceSharing />);
    await screen.findByText("One");
    expect(screen.getByText(/reached the maximum of 2/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Phone number, e.g. +491511234567")).not.toBeInTheDocument();
  });

  it("revokes a member using their user id, not the membership row id", async () => {
    vi.mocked(api.listMyWorkspaceMembers).mockResolvedValue([member({ id: "wm-row-1", member_id: "user-42" })]);
    vi.mocked(api.revokeWorkspaceMember).mockResolvedValue(undefined);
    render(<WorkspaceSharing />);
    fireEvent.click(await screen.findByText("Remove"));
    await waitFor(() => expect(api.revokeWorkspaceMember).toHaveBeenCalledWith("user-42"));
  });

  it("shows a pending invitation and accepts it", async () => {
    vi.mocked(api.listMyWorkspaceInvitations).mockResolvedValue([
      member({ status: "pending", owner_id: "owner-9", owner_display_name: "Owner Nine" }),
    ]);
    vi.mocked(api.acceptWorkspaceInvitation).mockResolvedValue(member({ status: "accepted" }));
    render(<WorkspaceSharing />);
    expect(await screen.findByText("Owner Nine invited you to their workspace")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Accept"));
    await waitFor(() => expect(api.acceptWorkspaceInvitation).toHaveBeenCalledWith("owner-9"));
  });

  it("declines a pending invitation", async () => {
    vi.mocked(api.listMyWorkspaceInvitations).mockResolvedValue([
      member({ status: "pending", owner_id: "owner-9", owner_display_name: "Owner Nine" }),
    ]);
    vi.mocked(api.declineWorkspaceInvitation).mockResolvedValue(member({ status: "declined" }));
    render(<WorkspaceSharing />);
    await screen.findByText("Owner Nine invited you to their workspace");

    fireEvent.click(screen.getByText("Decline"));
    await waitFor(() => expect(api.declineWorkspaceInvitation).toHaveBeenCalledWith("owner-9"));
  });

  it("lists workspaces shared with me", async () => {
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([
      member({ owner_display_name: "Generous Owner" }),
    ]);
    render(<WorkspaceSharing />);
    expect(await screen.findByText("Shared by Generous Owner")).toBeInTheDocument();
  });
});
