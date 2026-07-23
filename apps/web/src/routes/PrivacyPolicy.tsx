import { useTranslation } from "react-i18next";
import { LegalPageLayout } from "../components/LegalPageLayout";

export default function PrivacyPolicy() {
  const { t } = useTranslation();
  const sections = t("legalDocs.privacy.sections", { returnObjects: true }) as string[];

  return <LegalPageLayout title={t("legalDocs.privacy.title")} sections={sections} />;
}
