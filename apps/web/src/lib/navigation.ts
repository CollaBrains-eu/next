export const NAV_ITEMS: { to: string; labelKey: string }[] = [
  { to: "/", labelKey: "nav.dashboard" },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/chat", labelKey: "nav.aiChat" },
  { to: "/legal", labelKey: "nav.legalDraft" },
  { to: "/tasks", labelKey: "nav.tasks" },
  { to: "/entities", labelKey: "nav.entities" },
  { to: "/cases", labelKey: "nav.cases" },
  { to: "/vehicles", labelKey: "nav.vehicles" },
  { to: "/assistant", labelKey: "nav.assistant" },
  { to: "/settings", labelKey: "nav.settings" },
];

export function navItemsForRole(role: string | undefined): { to: string; labelKey: string }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", labelKey: "nav.admin" }];
}
