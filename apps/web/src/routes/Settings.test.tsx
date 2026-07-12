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
    vi.mocked(api.getPreferences).mockResolvedValue({
      preferred_language: "Nederlands",
      date_format: "eu",
      time_format: "h24",
    });
    vi.mocked(api.setPreferences).mockResolvedValue({
      preferred_language: "English",
      date_format: "us",
      time_format: "h12",
    });
  });

  it("loads and selects the saved preferred language", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
  });

  it("loads and selects the saved date and time format", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Date format")).toHaveValue("eu"));
    expect(screen.getByLabelText("Time format")).toHaveValue("h24");
  });

  it("saves the selected language, date format, and time format, and shows a confirmation", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.change(screen.getByLabelText("Preferred language"), { target: { value: "English" } });
    fireEvent.change(screen.getByLabelText("Date format"), { target: { value: "us" } });
    fireEvent.change(screen.getByLabelText("Time format"), { target: { value: "h12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.setPreferences).toHaveBeenCalledWith({
        preferredLanguage: "English",
        dateFormat: "us",
        timeFormat: "h12",
      }),
    );
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
