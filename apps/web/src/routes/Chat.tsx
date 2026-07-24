import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { ApiError, chat, submitFeedback, type ChatTurn, type Citation } from "../lib/api";
import { Button } from "../components/ui/Button";
import { ChatLog, type ChatTurnDisplay } from "../components/ui/ChatLog";
import { ChatInput } from "../components/ui/ChatInput";
import { useLoadingBar } from "../lib/loadingBar";
import { useToast } from "../lib/toast";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
  question?: string;
  confidence?: number | null;
  sufficientEvidence?: boolean | null;
  feedbackGiven?: "up" | "down" | null;
}

export default function Chat() {
  const { t } = useTranslation();
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { start, done } = useLoadingBar();
  const { showToast } = useToast();

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
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          question: message,
          confidence: response.confidence,
          sufficientEvidence: response.sufficient_evidence,
          feedbackGiven: null,
        },
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("chat.loadError"));
    } finally {
      setSending(false);
      done();
    }
  }

  async function handleFeedback(index: number, rating: "up" | "down") {
    const turn = turns[index];
    if (!turn || turn.feedbackGiven) return;
    setError(null);
    setTurns((prev) => prev.map((t, i) => (i === index ? { ...t, feedbackGiven: rating } : t)));
    try {
      await submitFeedback({
        endpoint: "chat",
        question: turn.question ?? "",
        answer: turn.content,
        rating,
        reflection_confidence: turn.confidence ?? null,
        reflection_sufficient_evidence: turn.sufficientEvidence ?? null,
      });
      showToast(t("chat.feedbackThanks"));
    } catch {
      setTurns((prev) => prev.map((t, i) => (i === index ? { ...t, feedbackGiven: null } : t)));
      setError(t("chat.feedbackError"));
    }
  }

  const displayTurns: ChatTurnDisplay[] = turns.map((turn, index) => ({
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
    confidence: turn.confidence,
    feedbackGiven: turn.feedbackGiven,
    onFeedback: turn.role === "assistant" ? (rating: "up" | "down") => handleFeedback(index, rating) : undefined,
  }));

  return (
    // `h-full` doesn't resolve here: Layout.tsx's <main> has no explicit height of
    // its own (only a `min-h-screen` floor inherited via the flex chain), so a
    // percentage height on this div just falls back to content size and the whole
    // page grows instead of ChatLog scrolling internally. Pin to the viewport
    // directly instead, minus the chrome that sits outside <main>'s content box:
    // mobile header (61px) + <main>'s padding (py-6 pb-24 = 24+96=120px) = 181px;
    // md+ has no header row (px-8 py-8 pb-8 = 32+32=64px).
    <div className="flex h-[calc(100dvh-181px)] flex-col gap-4 md:h-[calc(100dvh-64px)]">
      <h1 className="text-2xl font-semibold text-ink">{t("nav.aiChat")}</h1>

      <ChatLog
        turns={displayTurns}
        sending={sending}
        hint={t("chat.hint")}
        thinkingLabel={t("common.thinking")}
        lowConfidenceLabel={t("chat.lowConfidence")}
        thumbsUpLabel={t("chat.thumbsUp")}
        thumbsDownLabel={t("chat.thumbsDown")}
      />
      {error && <p className="text-sm text-danger">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <ChatInput value={input} onChange={setInput} placeholder={t("chat.inputPlaceholder")} disabled={sending} />
        <Button type="submit" disabled={sending || !input.trim()}>
          {t("common.send")}
        </Button>
      </form>
    </div>
  );
}
