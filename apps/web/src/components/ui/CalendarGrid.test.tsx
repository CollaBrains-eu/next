import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CalendarGrid } from "./CalendarGrid";

describe("CalendarGrid", () => {
  it("renders 42 day cells including leading/trailing days from adjacent months", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getAllByRole("button")).toHaveLength(42);
  });

  it("marks today with a distinct style and the selected date as pressed", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-20"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getByLabelText("2026-07-14")).toHaveClass("border-accent");
    expect(screen.getByLabelText("2026-07-20")).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a dot marker on days with at least one appointment", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set(["2026-07-14"])}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getByLabelText("2026-07-14").querySelector("span")).toBeInTheDocument();
    expect(screen.getByLabelText("2026-07-15").querySelector("span")).not.toBeInTheDocument();
  });

  it("calls onSelectDate with the clicked date's key", () => {
    const onSelectDate = vi.fn();
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={onSelectDate}
      />,
    );
    fireEvent.click(screen.getByLabelText("2026-07-21"));
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
  });
});
