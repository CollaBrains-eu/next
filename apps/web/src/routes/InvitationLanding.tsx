import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { acceptInvitation, checkInvitation, type InvitationCheckOut } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";
import { SkeletonLines } from "../components/ui/Skeleton";

type Status = "loading" | "valid" | "invalid";

export default function InvitationLanding() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, loginWithToken } = useAuth();
  const { token } = useParams<{ token: string }>();
  const [status, setStatus] = useState<Status>("loading");
  const [invitation, setInvitation] = useState<InvitationCheckOut | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return;
    }
    checkInvitation(token)
      .then((result) => {
        setInvitation(result);
        setStatus(result.valid ? "valid" : "invalid");
      })
      .catch(() => setStatus("invalid"));
  }, [token]);

  async function handleAccept() {
    if (!token) return;
    setAccepting(true);
    setError(null);
    try {
      const accessToken = await acceptInvitation(token);
      await loginWithToken(accessToken);
      navigate("/", { replace: true });
    } catch {
      setError(t("auth.invitationAcceptError"));
    } finally {
      setAccepting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 text-center shadow-raised">
        <div className="mb-6 flex items-center justify-center gap-2">
          <BrandMark size={32} />
          <span className="text-lg font-semibold text-ink">
            Collabr
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
              AI
            </span>
            ns
          </span>
        </div>

        {status === "loading" && <SkeletonLines />}

        {status === "invalid" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("auth.invitationInvalidTitle")}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("auth.invitationInvalidBody")}</p>
            <Link to="/login" className="mt-6 block">
              <Button variant="secondary" className="w-full">
                {t("auth.title")}
              </Button>
            </Link>
          </>
        )}

        {status === "valid" && invitation && (
          <>
            <h1 className="text-2xl font-semibold text-ink">
              {t("auth.invitationTitle", { org: invitation.organization_name })}
            </h1>
            <p className="mt-2 text-sm text-ink-2">{t("auth.invitationBody", { email: invitation.email })}</p>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            {user ? (
              <Button className="mt-6 w-full bg-gradient-brand hover:opacity-90" onClick={handleAccept} disabled={accepting}>
                {accepting ? t("auth.invitationAccepting") : t("auth.invitationAccept")}
              </Button>
            ) : invitation.account_exists ? (
              <Link to="/login" state={{ from: { pathname: `/invitations/${token}` } }} className="mt-6 block">
                <Button className="w-full bg-gradient-brand hover:opacity-90">{t("auth.invitationLogInToAccept")}</Button>
              </Link>
            ) : (
              <Link
                to={`/register?invitation=${token}`}
                className="mt-6 block"
              >
                <Button className="w-full bg-gradient-brand hover:opacity-90">{t("auth.invitationCreateAccount")}</Button>
              </Link>
            )}
          </>
        )}
      </div>
    </div>
  );
}
