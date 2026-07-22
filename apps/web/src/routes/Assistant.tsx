import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, askManager } from "../lib/api";
import { Button } from "../components/ui/Button";
import { ChatLog, type ChatTurnDisplay } from "../components/ui/ChatLog";
import { ChatInput } from "../components/ui/ChatInput";
import { useLoadingBar } from "../lib/loadingBar";

interface DisplayTurn {
  role: "user" | "assistant";
  content: string;
  toolCalled?: string | null;
}

export default function Assistant() {
  const { t } = useTranslation();
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { start, done } = useLoadingBar();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);
    start();

    try {
      const response = await askManager(message);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, toolCalled: response.tools_called[0] ?? null }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("assistant.loadError"));
    } finally {
      setSending(false);
      done();
    }
  }

  const displayTurns: ChatTurnDisplay[] = turns.map((turn) => ({
    role: turn.role,
    content: turn.content,
    footer: turn.toolCalled && (
      <div className="mt-2 border-t border-edge pt-2 text-xs text-ink-3">
        {t("assistant.toolCalled", { tool: turn.toolCalled })}
      </div>
    ),
  }));

  return (
    // See Chat.tsx for why this isn't `h-full`: Layout.tsx's <main> has no
    // explicit height of its own, so a percentage height here falls back to
    // content size and the page grows instead of ChatLog scrolling internally.
    <div className="flex h-[calc(100dvh-181px)] flex-col gap-4 md:h-[calc(100dvh-64px)]">
      <h1 className="text-2xl font-semibold text-ink">{t("nav.assistant")}</h1>

      <ChatLog turns={displayTurns} sending={sending} hint={t("assistant.hint")} thinkingLabel={t("common.thinking")} />
      {error && <p className="text-sm text-danger">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <ChatInput value={input} onChange={setInput} placeholder={t("assistant.inputPlaceholder")} disabled={sending} />
        <Button type="submit" disabled={sending || !input.trim()}>
          {t("common.send")}
        </Button>
      </form>
    </div>
  );
}
