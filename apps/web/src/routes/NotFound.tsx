import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import EmptyState from "../components/EmptyState";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto mt-16 max-w-sm">
      <h1 className="mb-4 text-center text-xl font-semibold text-ink">{t("notFound.title")}</h1>
      <EmptyState
        message={t("notFound.message")}
        action={
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors duration-base hover:bg-accent-hover"
          >
            {t("notFound.action")}
          </Link>
        }
      />
    </div>
  );
}
