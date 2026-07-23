import { useTranslation } from "react-i18next";
import { LegalPageLayout } from "../components/LegalPageLayout";

export default function TermsOfService() {
  const { t } = useTranslation();
  const sections = t("legalDocs.terms.sections", { returnObjects: true }) as string[];

  return <LegalPageLayout title={t("legalDocs.terms.title")} sections={sections} />;
}
