import { getMonthGridDates, toDateKey } from "../../lib/calendarGrid";

export function CalendarGrid({
  year,
  month,
  selectedDateKey,
  todayKey,
  appointmentDateKeys,
  onSelectDate,
}: {
  year: number;
  month: number;
  selectedDateKey: string;
  todayKey: string;
  appointmentDateKeys: Set<string>;
  onSelectDate: (dateKey: string) => void;
}) {
  const dates = getMonthGridDates(year, month);

  return (
    <div role="grid" aria-label="Month calendar" className="grid grid-cols-7 gap-1">
      {dates.map((date) => {
        const key = toDateKey(date);
        const inMonth = date.getMonth() === month;
        const isToday = key === todayKey;
        const isSelected = key === selectedDateKey;
        const hasAppointments = appointmentDateKeys.has(key);
        return (
          <button
            key={key}
            type="button"
            aria-label={key}
            aria-pressed={isSelected}
            onClick={() => onSelectDate(key)}
            className={[
              "flex flex-col items-center gap-0.5 rounded-lg p-2 text-sm transition-colors",
              inMonth ? "text-ink" : "text-ink-3",
              isSelected ? "bg-accent text-white" : isToday ? "border border-accent" : "hover:bg-accent-soft",
            ].join(" ")}
          >
            {date.getDate()}
            {hasAppointments && <span aria-hidden="true" className="h-1 w-1 rounded-full bg-accent" />}
          </button>
        );
      })}
    </div>
  );
}
