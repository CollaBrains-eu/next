import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isPasskeySupported } from "../lib/webauthn";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";

export default function Login() {
  const { t } = useTranslation();
  const { user, login, loginWithPasskey } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [passkeySubmitting, setPasskeySubmitting] = useState(false);

  if (user) {
    const from = (location.state as { from?: Location })?.from?.pathname ?? "/";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.loginError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasskeyLogin() {
    setError(null);
    setPasskeySubmitting(true);
    try {
      await loginWithPasskey();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.passkeyLoginError"));
    } finally {
      setPasskeySubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 shadow-raised">
        <div className="mb-6 flex items-center gap-2">
          <BrandMark size={32} />
          <span className="text-lg font-semibold text-ink">
            Collabr
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
              AI
            </span>
            ns
          </span>
        </div>

        <h1 className="text-2xl font-semibold text-ink">{t("auth.title")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("auth.subtitle")}</p>

        {isPasskeySupported() && (
          <>
            <Button
              type="button"
              variant="secondary"
              className="mt-6 w-full"
              onClick={handlePasskeyLogin}
              disabled={passkeySubmitting}
            >
              {passkeySubmitting ? t("auth.passkeySubmitting") : t("auth.passkeyLogin")}
            </Button>
            <div className="my-4 flex items-center gap-3 text-xs text-ink-2">
              <div className="h-px flex-1 bg-edge" />
              {t("auth.orDivider")}
              <div className="h-px flex-1 bg-edge" />
            </div>
          </>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <TextField
            label={t("auth.username")}
            value={username}
            onChange={setUsername}
            autoComplete="username"
            autoFocus
            required
          />
          <TextField
            label={t("auth.password")}
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            required
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={submitting} className="bg-gradient-brand hover:opacity-90">
            {submitting ? t("auth.submitting") : t("auth.submit")}
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-ink-2">
          {t("auth.noAccountYet")}{" "}
          <Link to="/register" className="font-medium text-accent hover:underline">
            {t("auth.registerTitle")}
          </Link>
        </p>
      </div>
    </div>
  );
}
