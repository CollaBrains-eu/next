import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { Dropdown } from "./ui/Dropdown";
import { Tooltip } from "./ui/Tooltip";
import { getPendingReviewEntityCount, listMyCaseInvitations } from "../lib/api";

export function AlertsBell() {
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [pendingInvitationCount, setPendingInvitationCount] = useState(0);
  const navigate = useNavigate();
  const { t } = useTranslation();

  useEffect(() => {
    // A real COUNT query, not listEntities(...).length -- that list endpoint caps at
    // limit=50, which silently undercounted this badge once the review queue grew past it.
    getPendingReviewEntityCount()
      .then(({ count }) => setPendingReviewCount(count))
      .catch(() => {
        // Alerts are a nice-to-have signal, not core navigation -- fail silently.
      });
    listMyCaseInvitations()
      .then((invitations) => setPendingInvitationCount(invitations.length))
      .catch(() => {});
  }, []);

  const pendingCount = pendingReviewCount + pendingInvitationCount;
  const options = [
    ...(pendingReviewCount > 0
      ? [{ label: t("alerts.pendingReviews", { count: pendingReviewCount }), onSelect: () => navigate("/entities/review") }]
      : []),
    ...(pendingInvitationCount > 0
      ? [{ label: t("alerts.pendingCaseInvitations", { count: pendingInvitationCount }), onSelect: () => navigate("/cases") }]
      : []),
    ...(pendingCount === 0 ? [{ label: t("alerts.empty"), onSelect: () => {} }] : []),
  ];

  return (
    <Tooltip label={t("alerts.title")}>
      <Dropdown
        trigger={
          <span
            aria-label={t("alerts.title")}
            className="relative flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M10 2.5a4 4 0 0 0-4 4v2.1c0 .53-.21 1.04-.59 1.41L4 11.5v1h12v-1l-1.41-1.49a2 2 0 0 1-.59-1.41V6.5a4 4 0 0 0-4-4Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M8.2 14.5a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            {pendingCount > 0 && (
              <span
                data-testid="alerts-bell-badge"
                className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white"
              >
                {pendingCount}
              </span>
            )}
          </span>
        }
        options={options}
        align="right"
      />
    </Tooltip>
  );
}
