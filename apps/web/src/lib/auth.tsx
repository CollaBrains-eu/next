import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, clearToken, fetchMe, getPreferences, login as apiLogin, setToken, type UserOut } from "./api";
import { toDateFormatPrefs } from "./dateFormat";
import i18n, { LANGUAGE_NAME_TO_CODE } from "./i18n";
import { setDateFormatPrefs } from "../hooks/useDateFormat";
import { loginWithPasskey as passkeyCeremony } from "./webauthn";

// The same preferred_language setting drives both the AI response language
// (api.preferences.build_language_instruction) and the UI language -- not a
// separate UI-only picker. Called on login and whenever Settings saves a change.
export function syncLanguage(preferredLanguage: string | null): void {
  const code = preferredLanguage ? LANGUAGE_NAME_TO_CODE[preferredLanguage] : undefined;
  i18n.changeLanguage(code ?? "en");
}

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithPasskey: () => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await fetchMe());
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        clearToken();
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    if (!user) return;
    getPreferences()
      .then((prefs) => {
        syncLanguage(prefs.preferred_language);
        setDateFormatPrefs(toDateFormatPrefs(prefs.date_format, prefs.time_format));
      })
      .catch(() => {
        // Preference sync is a nice-to-have; the defaults stay in effect on failure.
      });
  }, [user]);

  const login = useCallback(
    async (username: string, password: string) => {
      const token = await apiLogin(username, password);
      setToken(token);
      await refreshUser();
    },
    [refreshUser],
  );

  const loginWithPasskey = useCallback(async () => {
    const token = await passkeyCeremony();
    setToken(token);
    await refreshUser();
  }, [refreshUser]);

  // Shared by Register/VerifyEmail/InvitationLanding (Priority 3, ADR 0074):
  // those endpoints already return a fresh access_token directly (same
  // contract as /auth/token), so there's no separate credential exchange
  // step here, unlike login()/loginWithPasskey().
  const loginWithToken = useCallback(
    async (token: string) => {
      setToken(token);
      await refreshUser();
    },
    [refreshUser],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, loginWithPasskey, loginWithToken, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const { t } = useTranslation();

  if (loading) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}
