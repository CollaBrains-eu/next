import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  downloadAppointmentIcs,
  listAppointments,
  type AppointmentOut,
} from "../lib/api";
import { getMonthGridDates, toDateKey } from "../lib/calendarGrid";
import { Button } from "../components/ui/Button";
import { CalendarGrid } from "../components/ui/CalendarGrid";

export default function Calendar() {
  const { t } = useTranslation();
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDateKey, setSelectedDateKey] = useState(toDateKey(today));
  const [appointments, setAppointments] = useState<AppointmentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const gridDates = useMemo(() => getMonthGridDates(year, month), [year, month]);
  const todayKey = toDateKey(today);

  const refresh = useCallback(() => {
    setLoading(true);
    const from = toDateKey(gridDates[0]);
    const to = toDateKey(gridDates[gridDates.length - 1]);
    listAppointments(from, to)
      .then(setAppointments)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("calendar.loadError")))
      .finally(() => setLoading(false));
  }, [gridDates, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const appointmentDateKeys = useMemo(
    () => new Set(appointments.map((a) => toDateKey(new Date(a.starts_at)))),
    [appointments],
  );

  const dayAppointments = appointments
    .filter((a) => toDateKey(new Date(a.starts_at)) === selectedDateKey)
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));

  function goToPrevMonth() {
    const prev = new Date(year, month - 1, 1);
    setYear(prev.getFullYear());
    setMonth(prev.getMonth());
  }

  function goToNextMonth() {
    const next = new Date(year, month + 1, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth());
  }

  async function handleDownloadIcs(appointment: AppointmentOut) {
    const slug = appointment.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "appointment";
    await downloadAppointmentIcs(appointment.id, `${slug}.ics`);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("calendar.title")}</h1>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={goToPrevMonth} aria-label={t("calendar.prevMonth")}>
            ‹
          </Button>
          <Button size="sm" variant="ghost" onClick={goToNextMonth} aria-label={t("calendar.nextMonth")}>
            ›
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
        {!loading && (
          <CalendarGrid
            year={year}
            month={month}
            selectedDateKey={selectedDateKey}
            todayKey={todayKey}
            appointmentDateKeys={appointmentDateKeys}
            onSelectDate={setSelectedDateKey}
          />
        )}

        <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-4">
          {dayAppointments.length === 0 ? (
            <p className="text-sm text-ink-3">{t("calendar.noAppointments")}</p>
          ) : (
            dayAppointments.map((appointment) => (
              <div key={appointment.id} className="flex flex-col gap-1 border-b border-edge pb-3 last:border-0">
                <p className="text-sm font-medium text-ink">{appointment.title}</p>
                {appointment.notes && <p className="text-xs text-ink-2">{appointment.notes}</p>}
                <div className="mt-1 flex flex-wrap gap-2">
                  {appointment.location && (
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(appointment.location)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-accent hover:underline"
                    >
                      {t("calendar.openInMaps")}
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDownloadIcs(appointment)}
                    className="text-xs text-accent hover:underline"
                  >
                    {t("calendar.downloadIcs")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
