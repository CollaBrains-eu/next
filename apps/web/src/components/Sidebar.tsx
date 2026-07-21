import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { useSidebarCollapsed } from "../hooks/useSidebarCollapsed";
import { useCommandCenterState } from "../lib/commandCenter";
import { Button } from "./ui/Button";
import { Tooltip } from "./ui/Tooltip";
import { AlertsBell } from "./AlertsBell";
import { BrandMark } from "./BrandMark";
import { navItemsForRole } from "../lib/navigation";

export default function Sidebar({
  mobileOpen = false,
  onCloseMobile = () => {},
}: {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { collapsed, toggle: toggleCollapsed } = useSidebarCollapsed();
  const { openPalette } = useCommandCenterState();
  const { t } = useTranslation();
  const location = useLocation();
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ top: number; height: number }>({ top: 0, height: 0 });
  const navItems = navItemsForRole(user?.role);

  useEscapeToClose(mobileOpen, onCloseMobile);

  useEffect(() => {
    const activeItem = navItems.find((item) => (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)));
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) {
      setPillStyle({ top: el.offsetTop, height: el.offsetHeight });
    }
  }, [location.pathname, navItems, collapsed]);

  return (
    <>
      {mobileOpen && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 z-[70] bg-[#0D0C1A]/35 backdrop-blur-sm md:hidden"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-[71] flex w-56 shrink-0 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6 transition-transform duration-base ease-spring md:static md:z-auto md:h-screen md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "md:w-16" : "md:w-56"}`}
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <div className={`flex items-center gap-2 ${collapsed ? "md:justify-center" : ""}`}>
              <BrandMark size={28} />
              <span className={`whitespace-nowrap text-lg font-semibold text-ink ${collapsed ? "md:hidden" : ""}`}>
                Collabr
                <span
                  className="bg-clip-text text-transparent"
                  style={{ backgroundImage: "var(--gradient-brand)" }}
                >
                  AI
                </span>
                ns
              </span>
            </div>
            <div className={`flex items-center gap-1 ${collapsed ? "md:flex-col md:gap-2" : "justify-between"}`}>
              <Tooltip label={t("common.search")} className={collapsed ? "md:hidden" : ""}>
                <button
                  type="button"
                  aria-label={t("common.search")}
                  onClick={openPalette}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
                >
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M17 17l-4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
              </Tooltip>
              <AlertsBell />
              <button
                type="button"
                aria-label={collapsed ? t("common.expandSidebar") : t("common.collapseSidebar")}
                onClick={toggleCollapsed}
                className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink md:flex"
              >
                {collapsed ? (
                  <ChevronRight className="h-[18px] w-[18px]" aria-hidden="true" />
                ) : (
                  <ChevronLeft className="h-[18px] w-[18px]" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
          <nav className="relative flex flex-col gap-1 text-sm">
            <span
              data-testid="nav-pill"
              className="absolute left-0 right-0 z-0 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
              style={{ top: pillStyle.top, height: pillStyle.height }}
            />
            {navItems.map((item) => {
              const Icon = item.icon;
              const label = t(item.labelKey);
              const link = (
                <NavLink
                  key={item.to}
                  ref={(el) => {
                    itemRefs.current[item.to] = el;
                  }}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    `relative z-10 flex items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-fast ${
                      isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                  <span className={collapsed ? "md:sr-only" : ""}>{label}</span>
                </NavLink>
              );
              return collapsed ? (
                <Tooltip key={item.to} label={label} className="md:w-full">
                  {link}
                </Tooltip>
              ) : (
                link
              );
            })}
          </nav>
        </div>
        {user && (
          <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
            <span className={collapsed ? "md:sr-only" : ""}>{user.display_name}</span>
            <button onClick={logout} className={`text-left text-ink-2 hover:text-ink ${collapsed ? "md:sr-only" : ""}`}>
              {t("common.signOut")}
            </button>
            <Button variant="ghost" size="sm" onClick={toggle} className={`justify-start ${collapsed ? "md:sr-only" : ""}`}>
              {isDark ? t("common.lightMode") : t("common.darkMode")}
            </Button>
          </div>
        )}
      </aside>
    </>
  );
}
