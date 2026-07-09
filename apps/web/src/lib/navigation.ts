export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/vehicles", label: "Vehicles" },
  { to: "/assistant", label: "Assistant" },
  { to: "/settings", label: "Settings" },
];

export function navItemsForRole(role: string | undefined): { to: string; label: string }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", label: "Admin" }];
}
