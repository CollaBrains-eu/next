import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Calendar from "./Calendar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listAppointments: vi.fn(),
    createAppointment: vi.fn(),
    updateAppointment: vi.fn(),
    deleteAppointment: vi.fn(),
    downloadAppointmentIcs: vi.fn(),
    listCases: vi.fn(),
  };
});

const CASES: api.CaseOut[] = [
  {
    id: "case-1",
    name: "Smith v. Jones",
    description: null,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    document_count: 0,
    member_count: 0,
  },
];

const JULY_APPOINTMENTS: api.AppointmentOut[] = [
  {
    id: "a1",
    title: "APK inspection",
    starts_at: "2026-07-14T09:30:00Z",
    ends_at: null,
    location: "RDW Keuringsstation, Arnhem",
    notes: "Bring the kenteken papers",
    case_id: null,
    vehicle_id: null,
    created_at: "2026-07-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Calendar />
    </MemoryRouter>,
  );
}

describe("Calendar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] }); // leave setTimeout real so waitFor/findBy* polling still works
    vi.setSystemTime(new Date(2026, 6, 14));
    vi.mocked(api.listAppointments).mockResolvedValue(JULY_APPOINTMENTS);
    vi.mocked(api.listCases).mockResolvedValue(CASES);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches appointments for the visible month grid range and renders the day count", async () => {
    renderPage();
    await waitFor(() => expect(api.listAppointments).toHaveBeenCalledWith("2026-06-29", "2026-08-09"));
    expect(screen.getAllByRole("button", { name: /2026-07-\d\d/ })).toHaveLength(31);
  });

  it("shows the selected day's appointments in the agenda pane, defaulting to today", async () => {
    renderPage();
    expect(await screen.findByText("APK inspection")).toBeInTheDocument();
    expect(screen.getByText("Bring the kenteken papers")).toBeInTheDocument();
  });

  it("updates the agenda pane when a different day is clicked", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    fireEvent.click(screen.getByLabelText("2026-07-15"));
    await waitFor(() => expect(screen.queryByText("APK inspection")).not.toBeInTheDocument());
  });

  it("shows an Open in Maps link only when location is set", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    expect(
      screen.getByRole("link", { name: /open in maps/i }),
    ).toHaveAttribute(
      "href",
      "https://www.google.com/maps/search/?api=1&query=RDW%20Keuringsstation%2C%20Arnhem",
    );
  });

  it("downloads the .ics file when the download button is clicked", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    fireEvent.click(screen.getByRole("button", { name: /download .ics/i }));
    expect(api.downloadAppointmentIcs).toHaveBeenCalledWith("a1", "apk-inspection.ics");
  });
});

describe("Calendar create/edit/delete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] }); // leave setTimeout real so waitFor/findBy* polling still works
    vi.setSystemTime(new Date(2026, 6, 14));
    vi.mocked(api.listAppointments).mockResolvedValue(JULY_APPOINTMENTS);
    vi.mocked(api.listCases).mockResolvedValue(CASES);
    vi.mocked(api.createAppointment).mockResolvedValue({ ...JULY_APPOINTMENTS[0], id: "a2", title: "New one" });
    vi.mocked(api.updateAppointment).mockResolvedValue({ ...JULY_APPOINTMENTS[0], title: "Edited" });
    vi.mocked(api.deleteAppointment).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens the create modal, submits, and calls createAppointment", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByRole("button", { name: /new appointment/i }));
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "New one" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createAppointment).toHaveBeenCalled());
    const [payload] = vi.mocked(api.createAppointment).mock.calls[0];
    expect(payload.title).toBe("New one");
  });

  it("opens the edit modal pre-filled when an agenda item is clicked, and calls updateAppointment on submit", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByText("APK inspection"));
    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement;
    expect(titleInput.value).toBe("APK inspection");

    fireEvent.change(titleInput, { target: { value: "Edited" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.updateAppointment).toHaveBeenCalledWith("a1", expect.objectContaining({ title: "Edited" })));
  });

  it("deletes an appointment via the confirm modal", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByText("APK inspection"));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete appointment" }));

    await waitFor(() => expect(api.deleteAppointment).toHaveBeenCalledWith("a1"));
  });

  it("populates the case picker from listCases and includes the selection on create", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByRole("button", { name: /new appointment/i }));
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "New one" } });
    fireEvent.change(screen.getByLabelText(/case/i), { target: { value: "case-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createAppointment).toHaveBeenCalled());
    const [payload] = vi.mocked(api.createAppointment).mock.calls[0];
    expect(payload.case_id).toBe("case-1");
  });

  it("pre-selects the linked case when editing an appointment", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([{ ...JULY_APPOINTMENTS[0], case_id: "case-1" }]);
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByText("APK inspection"));
    const caseSelect = screen.getByLabelText(/case/i) as HTMLSelectElement;
    expect(caseSelect.value).toBe("case-1");
  });

  it("sends case_id: null when no case is selected", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByRole("button", { name: /new appointment/i }));
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "New one" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createAppointment).toHaveBeenCalled());
    const [payload] = vi.mocked(api.createAppointment).mock.calls[0];
    expect(payload.case_id).toBeNull();
  });
});
