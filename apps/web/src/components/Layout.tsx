import type { ReactNode } from "react";
import Navbar from "./Navbar";
import MobileTabBar from "./MobileTabBar";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page text-ink">
      <Navbar />
      <main className="mx-auto w-full max-w-screen-2xl flex-1 px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">
        {children}
      </main>
      <MobileTabBar />
    </div>
  );
}
