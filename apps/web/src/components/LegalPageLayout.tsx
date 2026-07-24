import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { BrandMark } from "./BrandMark";

// Priority 3 commercial SaaS (ADR 0074): these pages are structural
// placeholders, not real legal documents -- the actual policy text is a
// legal decision, not an engineering one, and is deliberately not written
// here. See each route file's section list and the notice banner this
// layout renders above them.
export function LegalPageLayout({ title, sections }: { title: string; sections: string[] }) {
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

        <h1 className="text-3xl font-semibold text-ink">{title}</h1>

        <div className="rounded-2xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-ink">
          <p className="font-semibold">{t("legalDocs.placeholderNoticeTitle")}</p>
          <p className="mt-1 text-ink-2">{t("legalDocs.placeholderNoticeBody")}</p>
        </div>

        <div className="flex flex-col gap-4">
          {sections.map((section) => (
            <section key={section} className="flex flex-col gap-1">
              <h2 className="text-lg font-semibold text-ink">{section}</h2>
              <p className="text-sm text-ink-3">{t("legalDocs.sectionPending")}</p>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
