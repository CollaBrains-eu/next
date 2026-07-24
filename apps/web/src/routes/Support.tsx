import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { BrandMark } from "../components/BrandMark";
import { Button } from "../components/ui/Button";

// Priority 3 commercial SaaS (ADR 0074): before this page, the only support
// affordance anywhere in the app was a bare mailto: link on the Enterprise
// pricing card. This is intentionally a single, honest contact point --
// not a fabricated FAQ or help-center article set nobody has actually
// written or reviewed.
export default function Support() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-page px-4 py-10">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div className="flex items-center gap-2">
          <BrandMark size={28} />
          <Link to="/" className="text-sm font-medium text-ink-2 hover:text-ink">
            {t("legalDocs.backToHome")}
          </Link>
        </div>

        <h1 className="text-3xl font-semibold text-ink">{t("support.title")}</h1>
        <p className="text-ink-2">{t("support.body")}</p>

        <a href="mailto:info@collabrains.eu" className="self-start">
          <Button>{t("support.emailCta")}</Button>
        </a>

        <div className="mt-4 flex flex-col gap-1">
          <Link to="/changelog" className="text-sm font-medium text-accent hover:underline">
            {t("support.changelogLink")}
          </Link>
        </div>
      </div>
    </div>
  );
}
