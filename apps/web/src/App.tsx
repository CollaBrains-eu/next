import { NavLink, Route, BrowserRouter, Routes } from "react-router-dom";
import Workspace from "./routes/Workspace";
import Chat from "./routes/Chat";
import NotFound from "./routes/NotFound";

const NAV_ITEMS = [
  { to: "/", label: "AI Workspace" },
  { to: "/chat", label: "AI Chat" },
];

function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-6">
          <span className="text-lg font-semibold">CollaBrains</span>
          <nav className="flex gap-4 text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  isActive ? "font-medium text-slate-900" : "text-slate-500 hover:text-slate-900"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Workspace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  );
}
