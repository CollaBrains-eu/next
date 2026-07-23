import { useTranslation } from "react-i18next";
import { LegalPageLayout } from "../components/LegalPageLayout";

export default function CookiePolicy() {
  const { t } = useTranslation();
  const sections = t("legalDocs.cookies.sections", { returnObjects: true }) as string[];

  return <LegalPageLayout title={t("legalDocs.cookies.title")} sections={sections} />;
}
