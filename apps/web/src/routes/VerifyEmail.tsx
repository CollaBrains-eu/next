import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { verifyEmail } from "../lib/api";
import { useAuth } from "../lib/auth";
import { consumePendingPlan } from "../lib/pendingPlan";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";
import { SkeletonLines } from "../components/ui/Skeleton";

type Status = "verifying" | "error";

export default function VerifyEmail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }
    verifyEmail(token)
      .then(async (accessToken) => {
        await loginWithToken(accessToken);
        const plan = consumePendingPlan();
        navigate(plan ? `/settings?checkout=${plan}` : "/", { replace: true });
      })
      .catch(() => setStatus("error"));
    // loginWithToken/navigate are stable (useCallback/react-router) --
    // this should only ever run once, for the token in the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

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

        {status === "verifying" && (
          <>
            <p className="text-sm text-ink-2">{t("auth.verifyingEmail")}</p>
            <div className="mt-4">
              <SkeletonLines />
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("auth.verifyEmailErrorTitle")}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("auth.verifyEmailErrorBody")}</p>
            <Link to="/register" className="mt-6 block">
              <Button variant="secondary" className="w-full">
                {t("auth.registerTitle")}
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
