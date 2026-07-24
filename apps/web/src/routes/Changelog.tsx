import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { BrandMark } from "../components/BrandMark";
import Card from "../components/Card";

// Priority 3 commercial SaaS (ADR 0074): starts from this phase's real,
// dated work rather than reconstructing every one of this project's 70+
// prior ADRs into changelog copy -- entries here are accurate as of when
// they were added, not an exhaustive product history.
const ENTRIES = [
  { date: "2026-07-23", key: "priority3" },
  { date: "2026-07-23", key: "priority2" },
  { date: "2026-07-23", key: "priority1" },
] as const;

export default function Changelog() {
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

        <h1 className="text-3xl font-semibold text-ink">{t("changelog.title")}</h1>
        <p className="text-ink-2">{t("changelog.intro")}</p>

        <div className="flex flex-col gap-4">
          {ENTRIES.map((entry) => (
            <Card key={entry.key} className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-3">{entry.date}</span>
              <h2 className="text-lg font-semibold text-ink">{t(`changelog.entries.${entry.key}.title`)}</h2>
              <p className="text-sm text-ink-2">{t(`changelog.entries.${entry.key}.body`)}</p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
