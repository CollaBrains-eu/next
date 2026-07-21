import {
  LayoutDashboard,
  FileText,
  Sparkles,
  Scale,
  CheckSquare,
  Calendar,
  Users,
  FolderOpen,
  Car,
  Bot,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export const NAV_ITEMS: { to: string; labelKey: string; icon: LucideIcon }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/documents", labelKey: "nav.documents", icon: FileText },
  { to: "/chat", labelKey: "nav.aiChat", icon: Sparkles },
  { to: "/legal", labelKey: "nav.legalDraft", icon: Scale },
  { to: "/tasks", labelKey: "nav.tasks", icon: CheckSquare },
  { to: "/calendar", labelKey: "nav.calendar", icon: Calendar },
  { to: "/entities", labelKey: "nav.entities", icon: Users },
  { to: "/cases", labelKey: "nav.cases", icon: FolderOpen },
  { to: "/vehicles", labelKey: "nav.vehicles", icon: Car },
  { to: "/assistant", labelKey: "nav.assistant", icon: Bot },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function navItemsForRole(role: string | undefined): { to: string; labelKey: string; icon: LucideIcon }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", labelKey: "nav.admin", icon: ShieldCheck }];
}
