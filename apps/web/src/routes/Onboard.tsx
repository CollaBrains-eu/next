import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { checkOnboardingToken } from "../lib/api";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { SkeletonLines } from "../components/ui/Skeleton";

type Status = "loading" | "valid" | "invalid";

export default function Onboard() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("loading");
  const [displayName, setDisplayName] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return;
    }
    checkOnboardingToken(token)
      .then((result) => {
        if (result.valid) {
          setDisplayName(result.display_name);
          setStatus("valid");
        } else {
          setStatus("invalid");
        }
      })
      .catch(() => setStatus("invalid"));
  }, [token]);

  return (
    <Card className="mx-auto mt-16 max-w-sm p-6 text-center">
      {status === "loading" && <SkeletonLines />}

      {status === "valid" && (
        <>
          <h1 className="text-2xl font-semibold text-ink">{t("onboard.welcomeTitle", { name: displayName })}</h1>
          <p className="mt-2 text-sm text-ink-2">{t("onboard.welcomeBody")}</p>
          <Link to="/login" className="mt-6 block">
            <Button className="w-full">{t("onboard.continueToLogin")}</Button>
          </Link>
        </>
      )}

      {status === "invalid" && (
        <>
          <h1 className="text-2xl font-semibold text-ink">{t("onboard.invalidTitle")}</h1>
          <p className="mt-2 text-sm text-ink-2">{t("onboard.invalidBody")}</p>
          <Link to="/login" className="mt-6 block">
            <Button variant="secondary" className="w-full">
              {t("onboard.continueToLogin")}
            </Button>
          </Link>
        </>
      )}
    </Card>
  );
}
