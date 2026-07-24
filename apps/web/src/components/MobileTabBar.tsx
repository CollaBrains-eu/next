import { NavLink } from "react-router";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";

interface TabItem {
  to: string;
  labelKey: string;
  end: boolean;
  icon: () => ReactElement;
}

function HomeIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M3 9.5 10 3l7 6.5M5 8v8a1 1 0 0 0 1 1h3v-5h2v5h3a1 1 0 0 0 1-1V8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DocsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 2.5h5.5L15 6v10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M11.5 2.5V6H15" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function DossiersIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M2.5 6a1 1 0 0 1 1-1h3.5l1.5 1.5H16a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V6Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ActiesIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M6.5 10.2 9 12.5l4.5-5.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const TAB_ITEMS: TabItem[] = [
  { to: "/", labelKey: "mobileNav.home", end: true, icon: HomeIcon },
  { to: "/documents", labelKey: "mobileNav.docs", end: false, icon: DocsIcon },
  { to: "/cases", labelKey: "mobileNav.dossiers", end: false, icon: DossiersIcon },
  { to: "/tasks", labelKey: "mobileNav.acties", end: false, icon: ActiesIcon },
];

function TabLink({ item, label }: { item: TabItem; label: string }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        `flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors duration-fast ${
          isActive ? "text-accent" : "text-ink-2"
        }`
      }
    >
      <Icon />
      <span>{label}</span>
    </NavLink>
  );
}

export default function MobileTabBar() {
  const { t } = useTranslation();

  return (
    <nav
      aria-label={t("mobileNav.navLabel")}
      className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-edge bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {TAB_ITEMS.slice(0, 2).map((item) => (
        <TabLink key={item.to} item={item} label={t(item.labelKey)} />
      ))}
      <div className="flex flex-1 items-center justify-center">
        <NavLink
          to="/documents"
          aria-label={t("mobileNav.upload")}
          className="-mt-6 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-overlay transition-transform duration-fast ease-spring active:scale-95"
        >
          <svg width="24" height="24" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </NavLink>
      </div>
      {TAB_ITEMS.slice(2).map((item) => (
        <TabLink key={item.to} item={item} label={t(item.labelKey)} />
      ))}
    </nav>
  );
}
