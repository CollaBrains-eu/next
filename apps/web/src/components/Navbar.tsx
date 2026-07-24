import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { ChevronDown, Menu } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useCommandCenterState } from "../lib/commandCenter";
import { Dropdown } from "./ui/Dropdown";
import { Tooltip } from "./ui/Tooltip";
import { Avatar } from "./ui/Avatar";
import { AlertsBell } from "./AlertsBell";
import { BrandMark } from "./BrandMark";
import { MobileNavDrawer } from "./MobileNavDrawer";
import { navItemsForRole } from "../lib/navigation";

const PRIMARY_PATHS = ["/", "/documents", "/cases", "/tasks", "/chat"];

function useMobileHeaderTitle(): string {
  const { t } = useTranslation();
  const location = useLocation();
  if (location.pathname === "/") return "CollaBrains";
  const item = navItemsForRole(undefined).find((i) => i.to !== "/" && location.pathname.startsWith(i.to));
  return item ? t(item.labelKey) : "CollaBrains";
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { openPalette } = useCommandCenterState();
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number }>({ left: 0, width: 0 });
  const title = useMobileHeaderTitle();

  const allItems = navItemsForRole(user?.role).filter((i) => i.to !== "/settings" && i.to !== "/admin");
  const primaryItems = allItems.filter((i) => PRIMARY_PATHS.includes(i.to));
  const secondaryItems = allItems.filter((i) => !PRIMARY_PATHS.includes(i.to));

  useEffect(() => {
    const activeItem = primaryItems.find((item) =>
      item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
    );
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) setPillStyle({ left: el.offsetLeft, width: el.offsetWidth });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const accountOptions = [
    { label: t("nav.settings"), onSelect: () => navigate("/settings") },
    ...(user?.role === "admin" ? [{ label: t("nav.admin"), onSelect: () => navigate("/admin") }] : []),
    { label: t("common.signOut"), onSelect: logout, danger: true },
  ];

  const moreOptions = secondaryItems.map((item) => ({
    label: t(item.labelKey),
    onSelect: () => navigate(item.to),
  }));

  return (
    <>
      <header className="sticky top-0 z-30 glass-surface border-b border-edge">
        {/* Desktop bar */}
        <div className="mx-auto hidden h-16 max-w-screen-2xl items-center justify-between gap-4 px-6 lg:flex">
          <NavLink to="/" className="flex shrink-0 items-center gap-2">
            <BrandMark size={28} />
            <span className="whitespace-nowrap text-lg font-semibold text-ink">
              Collabr
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
                AI
              </span>
              ns
            </span>
          </NavLink>

          <nav data-testid="navbar-primary-nav" className="relative flex flex-1 items-center gap-1">
            <span
              className="absolute bottom-1 z-0 h-9 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
              style={{ left: pillStyle.left, width: pillStyle.width }}
            />
            {primaryItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  ref={(el) => {
                    itemRefs.current[item.to] = el;
                  }}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `relative z-10 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-fast ${
                      isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                  {t(item.labelKey)}
                </NavLink>
              );
            })}
            <Dropdown
              trigger={
                <span className="relative z-10 flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-ink-2 transition-colors duration-fast hover:text-ink">
                  {t("common.more")}
                  <ChevronDown className="h-[14px] w-[14px]" aria-hidden="true" />
                </span>
              }
              options={moreOptions}
            />
          </nav>

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip label={t("common.search")}>
              <button
                type="button"
                aria-label={t("common.search")}
                onClick={openPalette}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
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
              aria-label={isDark ? t("common.lightMode") : t("common.darkMode")}
              onClick={toggle}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
            {user && (
              <Dropdown
                trigger={
                  <span className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink">
                    <Avatar name={user.display_name} size={28} />
                    <ChevronDown className="h-[14px] w-[14px]" aria-hidden="true" />
                  </span>
                }
                options={accountOptions}
              />
            )}
          </div>
        </div>

        {/* Mobile compact header */}
        <div className="flex items-center justify-between gap-2 px-4 py-3 lg:hidden">
          <div className="flex min-w-0 items-center gap-2">
            {user && (
              <NavLink to="/settings" aria-label={t("common.profile")}>
                <Avatar name={user.display_name} size={28} />
              </NavLink>
            )}
            <span data-testid="mobile-header-title" className="truncate text-lg font-semibold text-ink">
              {title}
            </span>
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
              {isDark ? "☀️" : "🌙"}
            </button>
            <button
              aria-label={t("common.openMenu")}
              onClick={() => setDrawerOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>
      <MobileNavDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  );
}
