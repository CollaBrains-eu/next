import { useState, type FormEvent } from "react";
import { ApiError, askManager } from "../lib/api";
import { Button } from "../components/ui/Button";
import { useLoadingBar } from "../lib/loadingBar";

interface DisplayTurn {
  role: "user" | "assistant";
  content: string;
  toolCalled?: string | null;
}

export default function Assistant() {
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
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, toolCalled: response.tool_called }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assistant request failed");
    } finally {
      setSending(false);
      done();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">Assistant</h1>

      <div className="flex flex-col gap-3">
        {turns.length === 0 && (
          <p className="text-sm text-ink-2">
            Ask the assistant to do something — it can choose and call tools on its own, unlike AI Chat which only
            answers from your documents.
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={
              turn.role === "user"
                ? "self-end max-w-[80%] rounded-2xl bg-accent px-4 py-2 text-sm text-white"
                : "max-w-[80%] rounded-2xl border border-edge bg-surface px-4 py-2 text-sm text-ink"
            }
          >
            <p className="whitespace-pre-wrap">{turn.content}</p>
            {turn.toolCalled && (
              <div className="mt-2 border-t border-edge pt-2 text-xs text-ink-3">
                via: {turn.toolCalled}
              </div>
            )}
          </div>
        ))}
        {sending && <p className="text-sm text-ink-3">Thinking…</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the assistant…"
          disabled={sending}
          className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}
