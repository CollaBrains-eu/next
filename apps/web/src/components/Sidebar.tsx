import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { Button } from "./ui/Button";

const NAV_ITEMS = [
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

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between border-r border-slate-200 bg-white px-4 py-6">
      <div className="flex flex-col gap-6">
        <span className="text-lg font-semibold">CollaBrains</span>
        <nav className="flex flex-col gap-1 text-sm">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-2 ${
                  isActive ? "bg-slate-100 font-medium text-slate-900" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      {user && (
        <div className="flex flex-col gap-2 border-t border-slate-200 pt-4 text-sm">
          <span className="text-slate-500">{user.display_name}</span>
          <button onClick={logout} className="text-left text-slate-500 hover:text-slate-900">
            Sign out
          </button>
          <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
            {isDark ? "☀️ Light mode" : "🌙 Dark mode"}
          </Button>
        </div>
      )}
    </aside>
  );
}
