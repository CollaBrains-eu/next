import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PhonePromptModal } from "./PhonePromptModal";
import { ApiError } from "../lib/api";
import * as api from "../lib/api";

const mockRefreshUser = vi.fn();
let mockUser: {
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
  phone_prompt_dismissed: boolean;
} | null = null;

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: mockUser, refreshUser: mockRefreshUser }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, linkPhoneNumber: vi.fn(), dismissPhonePrompt: vi.fn() };
});

const BASE_USER = {
  username: "alice", display_name: "Alice", email: "alice@collabrains.eu",
  role: "member", phone_number: null, phone_prompt_dismissed: false,
};

describe("PhonePromptModal", () => {
  beforeEach(() => {
    mockRefreshUser.mockReset();
    vi.mocked(api.linkPhoneNumber).mockReset();
    vi.mocked(api.dismissPhonePrompt).mockReset();
  });

  it("renders nothing when there is no user", () => {
    mockUser = null;
    render(<PhonePromptModal />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders nothing when the user already has a phone number", () => {
    mockUser = { ...BASE_USER, phone_number: "+15551230001" };
    render(<PhonePromptModal />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders nothing when the user already dismissed the prompt", () => {
    mockUser = { ...BASE_USER, phone_prompt_dismissed: true };
    render(<PhonePromptModal />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the prompt when the user has no phone and hasn't dismissed it", () => {
    mockUser = { ...BASE_USER };
    render(<PhonePromptModal />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("sets the phone number and refreshes the user", async () => {
    mockUser = { ...BASE_USER };
    vi.mocked(api.linkPhoneNumber).mockResolvedValue({ ...BASE_USER, phone_number: "+491511234567" });
    render(<PhonePromptModal />);

    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "+491511234567" } });
    fireEvent.click(screen.getByRole("button", { name: "Set phone number" }));

    await waitFor(() => expect(api.linkPhoneNumber).toHaveBeenCalledWith("+491511234567"));
    await waitFor(() => expect(mockRefreshUser).toHaveBeenCalled());
  });

  it("shows an error when setting the phone number fails", async () => {
    mockUser = { ...BASE_USER };
    vi.mocked(api.linkPhoneNumber).mockRejectedValue(new ApiError(400, "Invalid phone number"));
    render(<PhonePromptModal />);

    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Set phone number" }));

    expect(await screen.findByText("Invalid phone number")).toBeInTheDocument();
    expect(mockRefreshUser).not.toHaveBeenCalled();
  });

  it("skips the prompt and refreshes the user", async () => {
    mockUser = { ...BASE_USER };
    vi.mocked(api.dismissPhonePrompt).mockResolvedValue({ ...BASE_USER, phone_prompt_dismissed: true });
    render(<PhonePromptModal />);

    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    await waitFor(() => expect(api.dismissPhonePrompt).toHaveBeenCalled());
    await waitFor(() => expect(mockRefreshUser).toHaveBeenCalled());
  });
});
