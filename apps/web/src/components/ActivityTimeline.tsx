import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FileText, CheckSquare, FolderOpen, Users, type LucideIcon } from "lucide-react";
import { listDashboardActivity, type ActivityItemOut } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { DashboardWidgetCard } from "./DashboardWidgetCard";

const TYPE_ICON: Record<ActivityItemOut["type"], LucideIcon> = {
  document: FileText,
  task: CheckSquare,
  case: FolderOpen,
  entity: Users,
};

export function ActivityTimeline() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [items, setItems] = useState<ActivityItemOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDashboardActivity()
      .then(setItems)
      .catch(() => {
        // Same degrade-to-empty-state pattern as every other Dashboard widget.
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardWidgetCard
      title={t("dashboard.activityTimelineTitle")}
      loading={loading}
      isEmpty={items.length === 0}
      emptyMessage={t("dashboard.activityTimelineEmpty")}
    >
      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const Icon = TYPE_ICON[item.type];
          return (
            <li key={`${item.type}-${item.id}`} className="flex items-center gap-2 text-sm">
              <Icon className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
              <Link to={item.link} className="flex-1 truncate text-ink hover:text-accent">
                {item.title}
              </Link>
              <span className="shrink-0 text-xs text-ink-3">{formatDate(item.created_at)}</span>
            </li>
          );
        })}
      </ul>
    </DashboardWidgetCard>
  );
}
