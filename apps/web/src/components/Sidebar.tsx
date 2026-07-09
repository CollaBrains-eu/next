import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { Button } from "./ui/Button";
import { navItemsForRole } from "../lib/navigation";
import { listEntities } from "../lib/api";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const location = useLocation();
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ top: number; height: number }>({ top: 0, height: 0 });
  const [pendingCount, setPendingCount] = useState(0);
  const navItems = navItemsForRole(user?.role);

  useEffect(() => {
    const activeItem = navItems.find((item) => (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)));
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) {
      setPillStyle({ top: el.offsetTop, height: el.offsetHeight });
    }
  }, [location.pathname, navItems]);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review")
      .then((entities) => setPendingCount(entities.length))
      .catch(() => {
        // Badge is a nice-to-have signal, not core navigation -- fail silently.
      });
  }, []);

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6">
      <div className="flex flex-col gap-6">
        <span className="text-lg font-semibold text-ink">CollaBrains</span>
        <nav className="relative flex flex-col gap-1 text-sm">
          <span
            data-testid="nav-pill"
            className="absolute left-0 right-0 z-0 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
            style={{ top: pillStyle.top, height: pillStyle.height }}
          />
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              ref={(el) => {
                itemRefs.current[item.to] = el;
              }}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `relative z-10 flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-fast ${
                  isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                }`
              }
            >
              <span>{item.label}</span>
              {item.to === "/entities" && pendingCount > 0 && (
                <span
                  data-testid="entities-pending-badge"
                  className="rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-semibold text-white"
                >
                  {pendingCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
      {user && (
        <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
          <span className="text-ink-2">{user.display_name}</span>
          <button onClick={logout} className="text-left text-ink-2 hover:text-ink">
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
