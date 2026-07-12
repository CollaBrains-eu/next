import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { useDateFormat } from "../hooks/useDateFormat";
import {
  ApiError,
  approveResidency,
  correctResidency,
  listMyResidencies,
  listUserResidencies,
  rejectResidency,
  type ResidencyOut,
} from "../lib/api";

function formatAddressLine(residency: ResidencyOut): string {
  const { address } = residency;
  const parts = [
    [address.street, address.house_number].filter(Boolean).join(" "),
    [address.postal_code, address.city].filter(Boolean).join(" "),
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : address.name;
}

/** Address-history timeline for a user. Self-service (`userId` omitted, uses
 * /users/me/residencies) or admin viewing another user's history (`userId`
 * set, uses /admin/users/{id}/residencies -- read-only in that mode, no
 * approve/reject/correct actions since those are the owning user's calls
 * to make, admin can only observe). */
export function AddressHistory({ userId }: { userId?: string }) {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [residencies, setResidencies] = useState<ResidencyOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    const fetcher = userId ? listUserResidencies(userId) : listMyResidencies();
    fetcher
      .then(setResidencies)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("addressHistory.loadError")));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function handleApprove(id: string) {
    setBusyId(id);
    try {
      await approveResidency(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("addressHistory.actionError"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    try {
      await rejectResidency(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("addressHistory.actionError"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleCorrectValidFrom(id: string, currentValue: string | null) {
    const input = window.prompt(t("addressHistory.correctValidFromPrompt"), currentValue ?? "");
    if (!input) return;
    setBusyId(id);
    try {
      await correctResidency(id, { valid_from: input });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("addressHistory.actionError"));
    } finally {
      setBusyId(null);
    }
  }

  if (error) return <Alert variant="danger" title={t("addressHistory.loadError")}>{error}</Alert>;
  if (residencies === null) return <p className="text-sm text-ink-3">{t("common.loading")}</p>;
  if (residencies.length === 0) return <EmptyState message={t("addressHistory.empty")} />;

  return (
    <div className="flex flex-col gap-3">
      {residencies.map((residency) => (
        <Card key={residency.id} className="flex flex-col gap-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium text-ink">{formatAddressLine(residency)}</p>
              <p className="text-xs text-ink-3">
                {residency.valid_from ? formatDate(residency.valid_from) : "?"} &rarr;{" "}
                {residency.valid_to ? formatDate(residency.valid_to) : t("addressHistory.current")}
              </p>
            </div>
            {residency.status === "pending_review" ? (
              <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">
                {t("addressHistory.statusPendingReview")}
              </span>
            ) : residency.status === "confirmed" ? (
              <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success">
                {t("addressHistory.statusConfirmed")}
              </span>
            ) : (
              <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-ink-3">
                {t("addressHistory.statusRejected")}
              </span>
            )}
          </div>

          {residency.linked_document_count > 0 && (
            <p className="text-xs text-ink-3">
              {t("addressHistory.linkedDocuments", { count: residency.linked_document_count })}
              {residency.source_document_id && (
                <>
                  {" "}
                  &middot;{" "}
                  <Link to={`/documents/${residency.source_document_id}`} className="text-accent hover:underline">
                    {t("addressHistory.viewSourceDocument")}
                  </Link>
                </>
              )}
            </p>
          )}

          {!userId && (
            <div className="flex gap-2">
              {residency.status === "pending_review" && (
                <>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={busyId === residency.id}
                    onClick={() => handleApprove(residency.id)}
                  >
                    {t("addressHistory.approve")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busyId === residency.id}
                    onClick={() => handleReject(residency.id)}
                  >
                    {t("addressHistory.reject")}
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                size="sm"
                disabled={busyId === residency.id}
                onClick={() => handleCorrectValidFrom(residency.id, residency.valid_from)}
              >
                {t("addressHistory.correctDate")}
              </Button>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
