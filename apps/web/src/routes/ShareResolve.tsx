import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  resolveShareLink,
  type CaseDashboardOut,
  type DocumentDetailOut,
  type ShareResolveOut,
  type TaskOut,
} from "../lib/api";
import { ActivityTab } from "../components/ActivityTab";
import { Alert } from "../components/ui/Alert";
import { CaseDetailContent } from "../components/CaseDetailContent";
import { DocumentDetailContent } from "../components/DocumentDetailContent";
import { SkeletonLines } from "../components/ui/Skeleton";
import { TaskDetailContent } from "../components/TaskDetailContent";

export default function ShareResolve() {
  const { t } = useTranslation();
  const { token } = useParams<{ token: string }>();
  const [resolved, setResolved] = useState<ShareResolveOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!token) return;
    resolveShareLink(token)
      .then(setResolved)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("share.resolveError")));
  }, [token, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (error) {
    return (
      <Alert variant="danger" title={t("share.resolveError")}>
        {error}
      </Alert>
    );
  }

  if (!resolved) return <SkeletonLines className="max-w-md" />;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-ink">{t("share.viewingSharedTitle")}</h1>

      {resolved.entity_type === "document" && (
        <DocumentDetailContent document={resolved.data as DocumentDetailOut} onChanged={refresh} />
      )}
      {resolved.entity_type === "case" && (
        <CaseDetailContent caseData={resolved.data as CaseDashboardOut} onChanged={refresh} />
      )}
      {resolved.entity_type === "task" && (
        <TaskDetailContent task={resolved.data as TaskOut} onChanged={refresh} />
      )}

      <div>
        <h2 className="mb-2 text-sm font-medium text-ink-2">{t("drawer.activity")}</h2>
        <ActivityTab entityType={resolved.entity_type} entityId={(resolved.data as { id: string }).id} />
      </div>
    </div>
  );
}
