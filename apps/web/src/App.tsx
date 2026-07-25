import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router";
import { AnimatePresence, motion } from "framer-motion";
import { AuthProvider, ProtectedRoute, useAuth } from "./lib/auth";
import { AdminRoute } from "./components/AdminRoute";
import { ToastProvider } from "./lib/toast";
import { LoadingBarProvider, useLoadingBar } from "./lib/loadingBar";
import { CommandCenter } from "./components/CommandCenter";
import { CommandCenterStateProvider } from "./lib/commandCenter";
import { PhonePromptModal } from "./components/PhonePromptModal";
import { trackPageview } from "./lib/analytics";
import { clearOnboardingPending, needsOnboarding } from "./lib/onboardingFlag";
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
  // A freshly self-registered account (Register.tsx set this flag right
  // before email verification -- see lib/onboardingFlag.ts) sees the guided
  // workspace-setup wizard exactly once here, in place of the dashboard, the
  // first time it lands authenticated at "/". Re-checked on every render so
  // clearing the flag on completion immediately reveals the real dashboard
  // with the crossfade below, instead of a second navigation.
  const [showOnboarding, setShowOnboarding] = useState(() => needsOnboarding());

  if (loading) return null;
  if (!user) return <Landing />;

  // Rendered outside Layout (no sidebar/navbar chrome) while the wizard is
  // showing -- same standalone, full-screen treatment the token-claim variant
  // of this component already gets. Layout (and its sidebar/navbar) only
  // wraps the real dashboard.
  if (showOnboarding) {
    return (
      <AnimatePresence mode="wait">
        <motion.div key="onboard" exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
          <Onboard
            onComplete={() => {
              clearOnboardingPending();
              setShowOnboarding(false);
            }}
          />
        </motion.div>
      </AnimatePresence>
    );
  }

  return (
    <Layout>
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <Dashboard />
      </motion.div>
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
