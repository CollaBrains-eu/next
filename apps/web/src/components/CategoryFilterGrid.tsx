import { Briefcase, Coins, Home, Inbox, Shield, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { CategoryOut } from "../lib/api";

const PARENT_CATEGORY_ICON: Record<string, LucideIcon> = {
  finance: Coins,
  housing_vehicle: Home,
  insurance_care: Shield,
  work_education: Briefcase,
  government_identity: Shield,
  other_group: Inbox,
};

interface CategoryFilterGridProps {
  categories: CategoryOut[];
  activeIds: Set<string>;
  onToggleGroup: (childIds: string[]) => void;
  onToggleChild: (id: string) => void;
}

export function CategoryFilterGrid({ categories, activeIds, onToggleGroup, onToggleChild }: CategoryFilterGridProps) {
  const { t } = useTranslation();
  const parents = categories.filter((c) => c.parent_id === null);

  return (
    <div className="flex flex-wrap gap-3">
      {parents.map((parent) => {
        const children = categories.filter((c) => c.parent_id === parent.id);
        const childIds = children.map((c) => c.id);
        const groupActive = childIds.length > 0 && childIds.every((id) => activeIds.has(id));
        const Icon = PARENT_CATEGORY_ICON[parent.slug] ?? Inbox;

        return (
          <div key={parent.id} className="glass-surface flex min-w-[220px] flex-col gap-2 rounded-ds-lg p-3">
            <button
              type="button"
              onClick={() => onToggleGroup(childIds)}
              disabled={childIds.length === 0}
              className={`flex items-center gap-2 rounded-ds-md px-2 py-1 text-left text-sm font-medium transition-colors ${
                groupActive ? "bg-gradient-brand text-white" : "text-ink hover:bg-surface"
              }`}
            >
              <Icon size={16} />
              {t(`categories.${parent.slug}`)}
            </button>
            {children.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {children.map((child) => (
                  <button
                    key={child.id}
                    type="button"
                    onClick={() => onToggleChild(child.id)}
                    className={`rounded-ds-sm border px-2 py-0.5 text-xs transition-colors ${
                      activeIds.has(child.id)
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-edge text-ink-2 hover:border-accent"
                    }`}
                  >
                    {t(`categories.${child.slug}`)}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
