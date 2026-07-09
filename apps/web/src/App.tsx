import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, ProtectedRoute } from "./lib/auth";
import { AdminRoute } from "./components/AdminRoute";
import { ToastProvider } from "./lib/toast";
import { LoadingBarProvider, useLoadingBar } from "./lib/loadingBar";
import { CommandCenter } from "./components/CommandCenter";
import Layout from "./components/Layout";
import Login from "./routes/Login";
import Workspace from "./routes/Workspace";
import DocumentDetail from "./routes/DocumentDetail";
import Chat from "./routes/Chat";
import Legal from "./routes/Legal";
import Tasks from "./routes/Tasks";
import Entities from "./routes/Entities";
import EntityReview from "./routes/EntityReview";
import EntityGraph from "./routes/EntityGraph";
import Cases from "./routes/Cases";
import CaseDetail from "./routes/CaseDetail";
import Vehicles from "./routes/Vehicles";
import Assistant from "./routes/Assistant";
import Settings from "./routes/Settings";
import AdminDashboard from "./routes/AdminDashboard";
import NotFound from "./routes/NotFound";

function RouteChangeLoadingBar() {
  const location = useLocation();
  const { start, done } = useLoadingBar();
  const [lastPath, setLastPath] = useState(location.pathname);

  useEffect(() => {
    if (location.pathname === lastPath) return;
    setLastPath(location.pathname);
    start();
    const timer = setTimeout(done, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <LoadingBarProvider>
            <CommandCenter />
            <RouteChangeLoadingBar />
            <Layout>
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
                <Route
                  path="/entities"
                  element={
                    <ProtectedRoute>
                      <Entities />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/entities/review"
                  element={
                    <ProtectedRoute>
                      <EntityReview />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/entities/:id"
                  element={
                    <ProtectedRoute>
                      <EntityGraph />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/cases"
                  element={
                    <ProtectedRoute>
                      <Cases />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/cases/:id"
                  element={
                    <ProtectedRoute>
                      <CaseDetail />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/vehicles"
                  element={
                    <ProtectedRoute>
                      <Vehicles />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/assistant"
                  element={
                    <ProtectedRoute>
                      <Assistant />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/settings"
                  element={
                    <ProtectedRoute>
                      <Settings />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <AdminRoute>
                      <AdminDashboard />
                    </AdminRoute>
                  }
                />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Layout>
          </LoadingBarProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
