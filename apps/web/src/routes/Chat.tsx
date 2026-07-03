import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, chat, type ChatTurn, type Citation } from "../lib/api";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
}

export default function Chat() {
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const response = await chat(message, history);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, citations: response.citations }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat request failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">AI Chat</h1>

      <div className="flex flex-col gap-3">
        {turns.length === 0 && (
          <p className="text-sm text-slate-500">
            Ask a question about your documents. Answers are grounded only in retrieved content and cite sources.
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={
              turn.role === "user"
                ? "self-end max-w-[80%] rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
                : "max-w-[80%] rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm"
            }
          >
            <p className="whitespace-pre-wrap">{turn.content}</p>
            {turn.citations && turn.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
                {turn.citations.map((c) => (
                  <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-slate-900 hover:underline">
                    [{c.marker}] {c.document_title}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
        {sending && <p className="text-sm text-slate-400">Thinking…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={sending}
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
