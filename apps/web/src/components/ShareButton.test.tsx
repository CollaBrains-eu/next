import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ShareButton } from "./ShareButton";
import { ApiError } from "../lib/api";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, createShareLink: vi.fn() };
});

Object.assign(navigator, { clipboard: { writeText: vi.fn() } });

describe("ShareButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a share link and shows the URL in a modal", async () => {
    vi.mocked(api.createShareLink).mockResolvedValue({
      token: "tok123", url: "https://collabrains.eu/share/tok123", expires_at: "2026-08-01T00:00:00Z",
    });
    render(<ShareButton entityType="document" entityId="doc-1" />);

    fireEvent.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => expect(api.createShareLink).toHaveBeenCalledWith("document", "doc-1"));
    expect(await screen.findByDisplayValue("https://collabrains.eu/share/tok123")).toBeInTheDocument();
  });

  it("copies the link to the clipboard when Copy link is clicked", async () => {
    vi.mocked(api.createShareLink).mockResolvedValue({
      token: "tok123", url: "https://collabrains.eu/share/tok123", expires_at: "2026-08-01T00:00:00Z",
    });
    render(<ShareButton entityType="task" entityId="t1" />);

    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    fireEvent.click(await screen.findByRole("button", { name: "Copy link" }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("https://collabrains.eu/share/tok123");
  });

  it("shows an error message when creating the link fails", async () => {
    vi.mocked(api.createShareLink).mockRejectedValue(new ApiError(403, "Not allowed to share this task"));
    render(<ShareButton entityType="task" entityId="t1" />);

    fireEvent.click(screen.getByRole("button", { name: "Share" }));

    expect(await screen.findByText("Not allowed to share this task")).toBeInTheDocument();
  });
});
