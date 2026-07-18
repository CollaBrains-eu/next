import { useTranslation } from "react-i18next";
import Card from "./Card";
import { Button } from "./ui/Button";

export function TempPasswordCard({
  message,
  password,
  onDismiss,
}: {
  message: string;
  password: string;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Card className="flex flex-col gap-2 border-accent">
      <p className="text-sm font-medium text-ink">{message}</p>
      <p className="text-xs text-ink-3">{t("admin.tempPasswordHint")}</p>
      <code className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-ink" data-testid="temp-password">
        {password}
      </code>
      <div>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          {t("admin.dismiss")}
        </Button>
      </div>
    </Card>
  );
}
