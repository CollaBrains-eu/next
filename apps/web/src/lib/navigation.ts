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

export type NavGroup = "Overview" | "Records" | "Planning" | "AI Tools" | "Account";

export const NAV_ITEMS: { to: string; labelKey: string; icon: LucideIcon; group: NavGroup }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard, group: "Overview" },
  { to: "/documents", labelKey: "nav.documents", icon: FileText, group: "Records" },
  { to: "/entities", labelKey: "nav.entities", icon: Users, group: "Records" },
  { to: "/cases", labelKey: "nav.cases", icon: FolderOpen, group: "Records" },
  { to: "/vehicles", labelKey: "nav.vehicles", icon: Car, group: "Records" },
  { to: "/tasks", labelKey: "nav.tasks", icon: CheckSquare, group: "Planning" },
  { to: "/calendar", labelKey: "nav.calendar", icon: Calendar, group: "Planning" },
  { to: "/chat", labelKey: "nav.aiChat", icon: Sparkles, group: "AI Tools" },
  { to: "/legal", labelKey: "nav.legalDraft", icon: Scale, group: "AI Tools" },
  { to: "/assistant", labelKey: "nav.assistant", icon: Bot, group: "AI Tools" },
  { to: "/settings", labelKey: "nav.settings", icon: Settings, group: "Account" },
];

export function navItemsForRole(
  role: string | undefined
): { to: string; labelKey: string; icon: LucideIcon; group: NavGroup }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", labelKey: "nav.admin", icon: ShieldCheck, group: "Account" }];
}
