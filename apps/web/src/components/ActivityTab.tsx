import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listActivity, type ActivityLogEntryOut, type ShareableEntityType } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { SkeletonLines } from "./ui/Skeleton";

const ACTION_LABEL_KEYS: Record<string, string> = {
  uploaded: "activity.actionUploaded",
  classified: "activity.actionClassified",
  summarized: "activity.actionSummarized",
  reprocessed: "activity.actionReprocessed",
  deleted: "activity.actionDeleted",
  created: "activity.actionCreated",
  status_changed: "activity.actionStatusChanged",
  category_changed: "activity.actionCategoryChanged",
  moved: "activity.actionMoved",
  document_attached: "activity.actionDocumentAttached",
  task_attached: "activity.actionTaskAttached",
  decision_attached: "activity.actionDecisionAttached",
  vehicle_attached: "activity.actionVehicleAttached",
  member_invited: "activity.actionMemberInvited",
  member_removed: "activity.actionMemberRemoved",
};

export function ActivityTab({ entityType, entityId }: { entityType: ShareableEntityType; entityId: string }) {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
  const [items, setItems] = useState<ActivityLogEntryOut[] | null>(null);

  useEffect(() => {
    setItems(null);
    listActivity(entityType, entityId)
      .then(setItems)
      .catch(() => setItems([]));
  }, [entityType, entityId]);

  if (items === null) return <SkeletonLines />;
  if (items.length === 0) return <p className="text-sm text-ink-3">{t("activity.empty")}</p>;

  return (
    <ul className="flex flex-col gap-3">
      {items.map((item) => (
        <li key={item.id} className="text-sm">
          <span className="font-medium text-ink">{item.actor_display_name}</span>{" "}
          <span className="text-ink-2">
            {t(ACTION_LABEL_KEYS[item.action] ?? "activity.actionUnknown", { action: item.action })}
          </span>
          <div className="text-xs text-ink-3">{formatDateTime(item.created_at)}</div>
        </li>
      ))}
    </ul>
  );
}
