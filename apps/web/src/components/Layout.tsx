import { useState, type ReactNode } from "react";
import Sidebar from "./Sidebar";

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-page text-ink md:flex-row">
      <header className="flex items-center justify-between border-b border-edge bg-sidebar-surface px-4 py-3 md:hidden">
        <span className="text-lg font-semibold text-ink">CollaBrains</span>
        <button
          aria-label="Open menu"
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
      </header>
      <Sidebar mobileOpen={mobileNavOpen} onCloseMobile={() => setMobileNavOpen(false)} />
      <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">{children}</main>
    </div>
  );
}
