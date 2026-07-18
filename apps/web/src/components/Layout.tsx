import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Sidebar from "./Sidebar";
import MobileTabBar from "./MobileTabBar";
import { AlertsBell } from "./AlertsBell";
import { Avatar } from "./ui/Avatar";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useCommandCenterState } from "../lib/commandCenter";
import { NAV_ITEMS } from "../lib/navigation";

function useMobileHeaderTitle(): string {
  const { t } = useTranslation();
  const location = useLocation();
  if (location.pathname === "/") return "CollaBrains";
  const item = NAV_ITEMS.find((i) => i.to !== "/" && location.pathname.startsWith(i.to));
  return item ? t(item.labelKey) : "CollaBrains";
}

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { t } = useTranslation();
  const { user } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { openPalette } = useCommandCenterState();
  const title = useMobileHeaderTitle();

  return (
    <div className="flex min-h-screen flex-col bg-page text-ink md:flex-row">
      <header className="flex items-center justify-between gap-2 border-b border-edge bg-sidebar-surface px-4 py-3 md:hidden">
        <div className="flex min-w-0 items-center gap-2">
          {user && (
            <Link to="/settings" aria-label={t("common.profile")}>
              <Avatar name={user.display_name} size={28} />
            </Link>
          )}
          <span data-testid="mobile-header-title" className="truncate text-lg font-semibold text-ink">{title}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            aria-label={t("common.search")}
            onClick={openPalette}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
              <path d="M17 17l-4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <AlertsBell />
          <button
            type="button"
            aria-label={isDark ? t("common.lightMode") : t("common.darkMode")}
            onClick={toggle}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
          >
            {isDark ? (
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="10" cy="10" r="4" stroke="currentColor" strokeWidth="1.5" />
                <path
                  d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1 4.7 4.7"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M16.5 12.3A7 7 0 0 1 7.7 3.5a7 7 0 1 0 8.8 8.8Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
          <button
            aria-label={t("common.openMenu")}
            onClick={() => setMobileNavOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M3 5.5h14M3 10h14M3 14.5h14"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </header>
      <Sidebar mobileOpen={mobileNavOpen} onCloseMobile={() => setMobileNavOpen(false)} />
      <main className="flex-1 overflow-y-auto px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">{children}</main>
      <MobileTabBar />
    </div>
  );
}
