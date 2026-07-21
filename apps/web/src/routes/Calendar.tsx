import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createAppointment,
  deleteAppointment,
  downloadAppointmentIcs,
  listAppointments,
  listCases,
  updateAppointment,
  type AppointmentOut,
  type CaseOut,
} from "../lib/api";
import { fromDatetimeLocalValue, getMonthGridDates, toDateKey, toDatetimeLocalValue } from "../lib/calendarGrid";
import { buildMapsUrl } from "../lib/maps";
import { Button } from "../components/ui/Button";
import { CalendarGrid } from "../components/ui/CalendarGrid";
import { Modal } from "../components/ui/Modal";

export default function Calendar() {
  const { t } = useTranslation();
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDateKey, setSelectedDateKey] = useState(toDateKey(today));
  const [appointments, setAppointments] = useState<AppointmentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseOut[]>([]);

  useEffect(() => {
    listCases()
      .then(setCases)
      .catch(() => undefined);
  }, []);

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

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AppointmentOut | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formStartsAt, setFormStartsAt] = useState("");
  const [formLocation, setFormLocation] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [formCaseId, setFormCaseId] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function openCreateForm() {
    setEditing(null);
    setFormTitle("");
    setFormStartsAt(`${selectedDateKey}T09:00`);
    setFormLocation("");
    setFormNotes("");
    setFormCaseId("");
    setFormOpen(true);
  }

  function openEditForm(appointment: AppointmentOut) {
    setEditing(appointment);
    setFormTitle(appointment.title);
    setFormStartsAt(toDatetimeLocalValue(appointment.starts_at));
    setFormLocation(appointment.location ?? "");
    setFormNotes(appointment.notes ?? "");
    setFormCaseId(appointment.case_id ?? "");
    setFormOpen(true);
  }

  async function handleSubmitForm() {
    if (!formTitle.trim() || !formStartsAt) return;
    setSaving(true);
    try {
      const payload = {
        title: formTitle.trim(),
        starts_at: fromDatetimeLocalValue(formStartsAt),
        location: formLocation.trim() || undefined,
        notes: formNotes.trim() || undefined,
        case_id: formCaseId || null,
      };
      if (editing) {
        await updateAppointment(editing.id, payload);
      } else {
        await createAppointment(payload);
      }
      setFormOpen(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("calendar.createError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmDelete() {
    if (!editing) return;
    setDeleting(true);
    try {
      await deleteAppointment(editing.id);
      setConfirmDeleteOpen(false);
      setFormOpen(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("calendar.deleteError"));
    } finally {
      setDeleting(false);
    }
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
          <Button size="sm" variant="secondary" onClick={openCreateForm}>
            {t("calendar.newAppointment")}
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
                <button type="button" onClick={() => openEditForm(appointment)} className="text-left text-sm font-medium text-ink hover:underline">
                  {appointment.title}
                </button>
                {appointment.notes && <p className="text-xs text-ink-2">{appointment.notes}</p>}
                {appointment.case_id && (
                  <p className="text-xs text-ink-3">
                    {cases.find((c) => c.id === appointment.case_id)?.name}
                  </p>
                )}
                <div className="mt-1 flex flex-wrap gap-2">
                  {appointment.location && (
                    <a
                      href={buildMapsUrl(appointment.location)}
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

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? editing.title : t("calendar.newAppointment")}>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-title">
              {t("calendar.titleLabel")}
            </label>
            <input
              id="appointment-title"
              type="text"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-starts-at">
              {t("calendar.startsAtLabel")}
            </label>
            <input
              id="appointment-starts-at"
              type="datetime-local"
              value={formStartsAt}
              onChange={(e) => setFormStartsAt(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-location">
              {t("calendar.locationLabel")}
            </label>
            <input
              id="appointment-location"
              type="text"
              value={formLocation}
              onChange={(e) => setFormLocation(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-case">
              {t("calendar.caseLabel")}
            </label>
            <select
              id="appointment-case"
              value={formCaseId}
              onChange={(e) => setFormCaseId(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            >
              <option value="">{t("calendar.noCase")}</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-notes">
              {t("calendar.notesLabel")}
            </label>
            <textarea
              id="appointment-notes"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex justify-between gap-2">
            {editing && (
              <Button variant="danger" size="sm" onClick={() => setConfirmDeleteOpen(true)}>
                {t("common.delete")}
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setFormOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button size="sm" variant="primary" onClick={handleSubmitForm} disabled={saving || !formTitle.trim()}>
                {t("common.create")}
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={confirmDeleteOpen} onClose={() => setConfirmDeleteOpen(false)} title={t("calendar.deleteModalTitle")}>
        <p className="mb-4 text-sm text-ink-2">{t("calendar.deleteModalBody")}</p>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" size="sm" onClick={handleConfirmDelete} disabled={deleting}>
            {t("calendar.deleteConfirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
