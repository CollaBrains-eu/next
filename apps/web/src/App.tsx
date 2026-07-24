import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router";
import { AuthProvider, ProtectedRoute, useAuth } from "./lib/auth";
import { AdminRoute } from "./components/AdminRoute";
import { ToastProvider } from "./lib/toast";
import { LoadingBarProvider, useLoadingBar } from "./lib/loadingBar";
import { CommandCenter } from "./components/CommandCenter";
import { CommandCenterStateProvider } from "./lib/commandCenter";
import { PhonePromptModal } from "./components/PhonePromptModal";
import { trackPageview } from "./lib/analytics";
import Layout from "./components/Layout";
import Landing from "./routes/Landing";
import Login from "./routes/Login";
import Register from "./routes/Register";
import VerifyEmail from "./routes/VerifyEmail";
import InvitationLanding from "./routes/InvitationLanding";
import Onboard from "./routes/Onboard";
import PrivacyPolicy from "./routes/PrivacyPolicy";
import TermsOfService from "./routes/TermsOfService";
import CookiePolicy from "./routes/CookiePolicy";
import Support from "./routes/Support";
import Changelog from "./routes/Changelog";
import Dashboard from "./routes/Dashboard";
import Workspace from "./routes/Workspace";
import Chat from "./routes/Chat";
import Legal from "./routes/Legal";
import Tasks from "./routes/Tasks";
import Calendar from "./routes/Calendar";
import Entities from "./routes/Entities";
import EntityReview from "./routes/EntityReview";
import EntityGraph from "./routes/EntityGraph";
import Cases from "./routes/Cases";
import ShareResolve from "./routes/ShareResolve";
import Vehicles from "./routes/Vehicles";
import Assistant from "./routes/Assistant";
import Settings from "./routes/Settings";
import AdminDashboard from "./routes/AdminDashboard";
import NotFound from "./routes/NotFound";

function AnalyticsPageviews() {
  const location = useLocation();

  useEffect(() => {
    trackPageview();
  }, [location.pathname]);

  return null;
}

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

function RootRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Landing />;
  return (
    <Layout>
      <Dashboard />
    </Layout>
  );
}

function AppShell() {
  return (
    <Layout>
      <Routes>
        <Route
          path="/documents"
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
              <Workspace />
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
          path="/tasks/:id"
          element={
            <ProtectedRoute>
              <Tasks />
            </ProtectedRoute>
          }
        />
        <Route
          path="/calendar"
          element={
            <ProtectedRoute>
              <Calendar />
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
              <Cases />
            </ProtectedRoute>
          }
        />
        <Route
          path="/share/:token"
          element={
            <ProtectedRoute>
              <ShareResolve />
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
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <LoadingBarProvider>
            <CommandCenterStateProvider>
              <CommandCenter />
              <PhonePromptModal />
              <RouteChangeLoadingBar />
              <AnalyticsPageviews />
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/verify-email" element={<VerifyEmail />} />
                <Route path="/invitations/:token" element={<InvitationLanding />} />
                <Route path="/onboard" element={<Onboard />} />
                <Route path="/privacy" element={<PrivacyPolicy />} />
                <Route path="/terms" element={<TermsOfService />} />
                <Route path="/cookies" element={<CookiePolicy />} />
                <Route path="/support" element={<Support />} />
                <Route path="/changelog" element={<Changelog />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
            </CommandCenterStateProvider>
          </LoadingBarProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
