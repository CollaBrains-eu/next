import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, chat, type ChatTurn, type Citation } from "../lib/api";
import { Button } from "../components/ui/Button";
import { ChatLog, type ChatTurnDisplay } from "../components/ui/ChatLog";
import { useLoadingBar } from "../lib/loadingBar";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
}

export default function Chat() {
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

    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);
    start();

    try {
      const response = await chat(message, history);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, citations: response.citations }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("chat.loadError"));
    } finally {
      setSending(false);
      done();
    }
  }

  const displayTurns: ChatTurnDisplay[] = turns.map((turn) => ({
    role: turn.role,
    content: turn.content,
    footer: turn.citations && turn.citations.length > 0 && (
      <div className="mt-2 flex flex-wrap gap-2 border-t border-edge pt-2 text-xs text-ink-3">
        {turn.citations.map((c) => (
          <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-accent hover:underline">
            [{c.marker}] {c.document_title}
          </Link>
        ))}
      </div>
    ),
  }));

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("nav.aiChat")}</h1>

      <div className="flex flex-col gap-3">
        <ChatLog turns={displayTurns} sending={sending} hint={t("chat.hint")} thinkingLabel={t("common.thinking")} />
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.inputPlaceholder")}
          disabled={sending}
          className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          {t("common.send")}
        </Button>
      </form>
    </div>
  );
}
