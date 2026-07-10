import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Card from "./Card";
import { Skeleton } from "./ui/Skeleton";

export function DashboardWidgetCard({
  title,
  loading,
  isEmpty,
  emptyMessage,
  children,
  actions,
}: {
  title: string;
  loading: boolean;
  isEmpty: boolean;
  emptyMessage: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const { t } = useTranslation();

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            aria-expanded={!collapsed}
            aria-label={
              collapsed ? t("dashboard.expandWidget", { title }) : t("dashboard.collapseWidget", { title })
            }
            onClick={() => setCollapsed((v) => !v)}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-3 transition-colors duration-fast hover:bg-hover hover:text-ink"
          >
            {collapsed ? "+" : "–"}
          </button>
        </div>
      </div>
      {!collapsed &&
        (loading ? (
          <div className="flex flex-col gap-2" data-testid="widget-skeleton">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : isEmpty ? (
          <p className="text-sm text-ink-2">{emptyMessage}</p>
        ) : (
          children
        ))}
    </Card>
  );
}
