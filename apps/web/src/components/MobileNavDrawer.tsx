import { NavLink } from "react-router";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { Button } from "./ui/Button";
import { navItemsForRole } from "../lib/navigation";

export function MobileNavDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { t } = useTranslation();
  const navItems = navItemsForRole(user?.role);

  useEscapeToClose(open, onClose);

  return (
    <>
      {open && (
        <div
          data-testid="mobile-nav-backdrop"
          className="fixed inset-0 z-[70] bg-[#0D0C1A]/35 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-[71] flex w-64 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6 transition-transform duration-base ease-spring lg:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <nav className="flex flex-col gap-1 text-sm">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-fast ${
                    isActive ? "bg-accent-soft font-semibold text-accent" : "text-ink-2 hover:bg-hover hover:text-ink"
                  }`
                }
              >
                <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                {t(item.labelKey)}
              </NavLink>
            );
          })}
        </nav>
        {user && (
          <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
            <span>{user.display_name}</span>
            <button onClick={logout} className="text-left text-ink-2 hover:text-ink">
              {t("common.signOut")}
            </button>
            <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
              {isDark ? t("common.lightMode") : t("common.darkMode")}
            </Button>
          </div>
        )}
      </aside>
    </>
  );
}
