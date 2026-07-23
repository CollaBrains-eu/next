import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, checkInvitation, registerAccount } from "../lib/api";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";

export default function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const invitationToken = searchParams.get("invitation");

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [invitedOrgName, setInvitedOrgName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  useEffect(() => {
    if (!invitationToken) return;
    checkInvitation(invitationToken)
      .then((result) => {
        if (result.valid) {
          setInvitedOrgName(result.organization_name);
          if (result.email) setEmail(result.email);
        }
      })
      .catch(() => {
        // Invalid/expired invitation still lets someone register on their own.
      });
  }, [invitationToken]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await registerAccount({
        username,
        displayName,
        email,
        password,
        organizationName: invitationToken ? undefined : organizationName || undefined,
        invitationToken: invitationToken ?? undefined,
      });
      setEmailSent(result.email_sent);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.registerError"));
    } finally {
      setSubmitting(false);
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

        {submitted ? (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("auth.registerCheckEmailTitle")}</h1>
            <p className="mt-2 text-sm text-ink-2">
              {emailSent ? t("auth.registerCheckEmailBody", { email }) : t("auth.registerEmailNotSentBody")}
            </p>
            <Button variant="secondary" className="mt-6 w-full" onClick={() => navigate("/login")}>
              {t("onboard.continueToLogin")}
            </Button>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("auth.registerTitle")}</h1>
            <p className="mt-1 text-sm text-ink-2">
              {invitedOrgName ? t("auth.registerInvitedSubtitle", { org: invitedOrgName }) : t("auth.registerSubtitle")}
            </p>

            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
              <TextField
                label={t("auth.displayName")}
                value={displayName}
                onChange={setDisplayName}
                autoComplete="name"
                autoFocus
                required
              />
              <TextField
                label={t("auth.username")}
                value={username}
                onChange={setUsername}
                autoComplete="username"
                required
              />
              <TextField
                label={t("auth.email")}
                type="email"
                value={email}
                onChange={setEmail}
                autoComplete="email"
                required
                disabled={Boolean(invitationToken)}
              />
              <TextField
                label={t("auth.password")}
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                required
              />
              {!invitationToken && (
                <TextField
                  label={t("auth.organizationName")}
                  value={organizationName}
                  onChange={setOrganizationName}
                  placeholder={t("auth.organizationNamePlaceholder")}
                />
              )}
              {error && <p className="text-sm text-danger">{error}</p>}
              <Button type="submit" disabled={submitting} className="bg-gradient-brand hover:opacity-90">
                {submitting ? t("auth.registerSubmitting") : t("auth.registerSubmit")}
              </Button>
            </form>

            <p className="mt-4 text-center text-sm text-ink-2">
              {t("auth.alreadyHaveAccount")}{" "}
              <Link to="/login" className="font-medium text-accent hover:underline">
                {t("auth.title")}
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
