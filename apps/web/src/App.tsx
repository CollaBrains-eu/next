import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedRoute, useAuth } from "./lib/auth";
import Login from "./routes/Login";
import Workspace from "./routes/Workspace";
import DocumentDetail from "./routes/DocumentDetail";
import Chat from "./routes/Chat";
import Legal from "./routes/Legal";
import Tasks from "./routes/Tasks";
import NotFound from "./routes/NotFound";

const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
];

function HeaderUser() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-slate-500">{user.display_name}</span>
      <button onClick={logout} className="text-slate-500 hover:text-slate-900">
        Sign out
      </button>
    </div>
  );
}

function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
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
          <HeaderUser />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Workspace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/documents/:id"
            element={
              <ProtectedRoute>
                <DocumentDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />
          <Route
            path="/legal"
            element={
              <ProtectedRoute>
                <Legal />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <Tasks />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout />
      </AuthProvider>
    </BrowserRouter>
  );
}
