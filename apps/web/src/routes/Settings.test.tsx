import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getPreferences: vi.fn(),
    setPreferences: vi.fn(),
  };
});

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getPreferences).mockResolvedValue({ preferred_language: "Nederlands" });
    vi.mocked(api.setPreferences).mockResolvedValue({ preferred_language: "English" });
  });

  it("loads and selects the saved preferred language", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
  });

  it("saves the selected language and shows a confirmation", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.change(screen.getByLabelText("Preferred language"), { target: { value: "English" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.setPreferences).toHaveBeenCalledWith("English"));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("shows an error message when saving fails", async () => {
    vi.mocked(api.setPreferences).mockRejectedValue(new api.ApiError(500, "Save boom"));
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Save boom")).toBeInTheDocument();
  });
});
