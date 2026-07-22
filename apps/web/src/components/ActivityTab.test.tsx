import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActivityTab } from "./ActivityTab";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listActivity: vi.fn() };
});

describe("ActivityTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton before the activity resolves", () => {
    vi.mocked(api.listActivity).mockReturnValue(new Promise(() => {}));
    render(<ActivityTab entityType="document" entityId="doc-1" />);
    expect(screen.getByTestId("skeleton-lines")).toBeInTheDocument();
  });

  it("shows an empty state when there is no activity", async () => {
    vi.mocked(api.listActivity).mockResolvedValue([]);
    render(<ActivityTab entityType="document" entityId="doc-1" />);
    expect(await screen.findByText("No activity yet.")).toBeInTheDocument();
  });

  it("renders entries with the actor's name and a formatted action label", async () => {
    vi.mocked(api.listActivity).mockResolvedValue([
      {
        id: "a1", entity_type: "document", entity_id: "doc-1", action: "uploaded",
        actor_user_id: "u1", actor_display_name: "Ada Admin", detail: {}, created_at: "2026-07-20T10:00:00Z",
      },
    ]);
    render(<ActivityTab entityType="document" entityId="doc-1" />);

    expect(await screen.findByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("uploaded this")).toBeInTheDocument();
  });

  it("falls back gracefully for an unrecognized action string", async () => {
    vi.mocked(api.listActivity).mockResolvedValue([
      {
        id: "a1", entity_type: "task", entity_id: "t1", action: "some_future_action",
        actor_user_id: "u1", actor_display_name: "Ada Admin", detail: {}, created_at: "2026-07-20T10:00:00Z",
      },
    ]);
    render(<ActivityTab entityType="task" entityId="t1" />);

    expect(await screen.findByText("some_future_action")).toBeInTheDocument();
  });
});
