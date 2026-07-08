import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedRoute } from "./lib/auth";
import { ToastProvider } from "./lib/toast";
import Layout from "./components/Layout";
import Login from "./routes/Login";
import Workspace from "./routes/Workspace";
import DocumentDetail from "./routes/DocumentDetail";
import Chat from "./routes/Chat";
import Legal from "./routes/Legal";
import Tasks from "./routes/Tasks";
import Entities from "./routes/Entities";
import EntityGraph from "./routes/EntityGraph";
import Cases from "./routes/Cases";
import CaseDetail from "./routes/CaseDetail";
import Vehicles from "./routes/Vehicles";
import Assistant from "./routes/Assistant";
import Settings from "./routes/Settings";
import NotFound from "./routes/NotFound";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
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
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Layout>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
