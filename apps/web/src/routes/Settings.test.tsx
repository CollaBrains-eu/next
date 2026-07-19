import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import { AuthProvider } from "../lib/auth";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getPreferences: vi.fn(),
    setPreferences: vi.fn(),
    fetchMe: vi.fn(),
    getOrganization: vi.fn(),
    listOrganizationMembers: vi.fn(),
    renameOrganization: vi.fn(),
    setOrganizationPolicies: vi.fn(),
  };
});

const MEMBERS = [
  { id: "u1", username: "amember", display_name: "A Member", role: "member" },
  { id: "u2", username: "badmin", display_name: "B Admin", role: "admin" },
];

function renderPage() {
  return render(
    <AuthProvider>
      <ToastProvider>
        <Settings />
      </ToastProvider>
    </AuthProvider>
  );
}

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // null (not "Nederlands") so AuthProvider's own preference-sync effect
    // (which also calls syncLanguage) doesn't switch the shared, global
    // i18n instance to Dutch and corrupt every other test's English
    // string assertions -- the one test that needs "Nederlands" as the
    // loaded value overrides this mock locally.
    vi.mocked(api.getPreferences).mockResolvedValue({
      preferred_language: null,
      date_format: "eu",
      time_format: "h24",
    });
    vi.mocked(api.setPreferences).mockResolvedValue({
      preferred_language: "English",
      date_format: "us",
      time_format: "h12",
    });
    vi.mocked(api.fetchMe).mockResolvedValue({
      username: "member1", display_name: "Member One", email: null, role: "member",
      phone_number: null, phone_prompt_dismissed: true,
    });
    vi.mocked(api.getOrganization).mockResolvedValue({
      id: "org1", name: "Acme Legal", policies: { approval_required_goals: ["draft_legal_document"] },
    });
    vi.mocked(api.listOrganizationMembers).mockResolvedValue(MEMBERS);
    vi.mocked(api.renameOrganization).mockResolvedValue({ id: "org1", name: "Renamed Inc", policies: {} });
    vi.mocked(api.setOrganizationPolicies).mockResolvedValue({
      id: "org1", name: "Acme Legal", policies: { approval_required_goals: ["summarize_case"] },
    });
  });

  it("loads and selects the saved preferred language", async () => {
    vi.mocked(api.getPreferences).mockResolvedValue({
      preferred_language: "Nederlands",
      date_format: "eu",
      time_format: "h24",
    });
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
  });

  it("loads and selects the saved date and time format", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Date format")).toHaveValue("eu"));
    expect(screen.getByLabelText("Time format")).toHaveValue("h24");
  });

  it("saves the selected language, date format, and time format, and shows a confirmation", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue(""));
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
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue(""));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Save boom")).toBeInTheDocument();
  });

  describe("Organization section", () => {
    it("shows the org name and member roster read-only for a non-admin, with no edit controls", async () => {
      renderPage();
      expect(await screen.findByText("Acme Legal")).toBeInTheDocument();
      expect(screen.getByText(/A Member/)).toBeInTheDocument();
      expect(screen.getByText(/B Admin/)).toBeInTheDocument();
      expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
      expect(screen.queryByText("Goals requiring approval")).not.toBeInTheDocument();
    });

    it("shows an editable name field and policy picker for an admin", async () => {
      vi.mocked(api.fetchMe).mockResolvedValue({
        username: "admin1", display_name: "Admin One", email: null, role: "admin",
        phone_number: null, phone_prompt_dismissed: true,
      });
      renderPage();
      expect(await screen.findByLabelText("Name")).toHaveValue("Acme Legal");
      expect(screen.getByText("Goals requiring approval")).toBeInTheDocument();
      expect(screen.getByLabelText("Remove Draft legal document")).toBeInTheDocument();
    });

    it("saves the renamed org and updated policies, and shows a confirmation toast", async () => {
      vi.mocked(api.fetchMe).mockResolvedValue({
        username: "admin1", display_name: "Admin One", email: null, role: "admin",
        phone_number: null, phone_prompt_dismissed: true,
      });
      renderPage();
      const nameField = await screen.findByLabelText("Name");
      fireEvent.change(nameField, { target: { value: "Renamed Inc" } });

      const saveButtons = screen.getAllByRole("button", { name: "Save" });
      fireEvent.click(saveButtons[saveButtons.length - 1]);

      await waitFor(() => expect(api.renameOrganization).toHaveBeenCalledWith("Renamed Inc"));
      expect(api.setOrganizationPolicies).toHaveBeenCalledWith({ approval_required_goals: ["draft_legal_document"] });
      expect(await screen.findByText("Organization settings saved.")).toBeInTheDocument();
    });
  });
});
