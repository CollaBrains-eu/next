import { useEffect, useRef, type ReactNode } from "react";
import { Badge } from "./Badge";

// Below this, the model itself flagged the answer as under-evidenced
// enough to be worth a visible nudge -- see reflection.py's confidence
// scale (0-100).
const LOW_CONFIDENCE_THRESHOLD = 60;

export interface ChatTurnDisplay {
  role: "user" | "assistant";
  content: string;
  footer?: ReactNode;
  confidence?: number | null;
  feedbackGiven?: "up" | "down" | null;
  onFeedback?: (rating: "up" | "down") => void;
}

function ThumbIcon({ down = false }: { down?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={down ? { transform: "rotate(180deg)" } : undefined}>
      <path
        d="M6 14V7l3-5.5c.3-.5.9-.7 1.4-.3.4.3.6.8.5 1.3L10 7h3.5c.8 0 1.5.7 1.4 1.5l-.8 5c-.1.8-.8 1.5-1.7 1.5H6Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path d="M6 14H3.5A1.5 1.5 0 0 1 2 12.5V8.5A1.5 1.5 0 0 1 3.5 7H6v7Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Shared bubble log for Chat.tsx and Assistant.tsx -- both pages sent turns
 * through the same hand-rolled markup before this, one with citation links
 * as the footer, one with the called-tool name. Bubbles get the artifact's
 * asymmetric "speech bubble" corner (small radius on the side pointing at
 * the sender) instead of a uniform rounded-2xl on both.
 */
export function ChatLog({
  turns,
  sending,
  hint,
  thinkingLabel,
  lowConfidenceLabel,
  thumbsUpLabel,
  thumbsDownLabel,
}: {
  turns: ChatTurnDisplay[];
  sending: boolean;
  hint?: string;
  thinkingLabel: string;
  lowConfidenceLabel?: string;
  thumbsUpLabel?: string;
  thumbsDownLabel?: string;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // optional chaining on the call itself, not just the ref: jsdom (this
    // project's test environment) doesn't implement scrollIntoView at all
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, sending]);

  if (turns.length === 0) {
    return hint ? (
      <div className="flex min-h-0 flex-1 flex-col">
        <p className="text-sm text-ink-2">{hint}</p>
      </div>
    ) : (
      <div className="min-h-0 flex-1" />
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      {turns.map((turn, i) => (
        <div
          key={i}
          className={
            turn.role === "user"
              ? "self-end max-w-[80%] rounded-ds-lg rounded-br-sm bg-gradient-brand px-4 py-2 text-sm text-white"
              : "glass-surface max-w-[80%] rounded-ds-lg rounded-bl-sm border border-edge px-4 py-2 text-sm text-ink"
          }
        >
          <p className="whitespace-pre-wrap">{turn.content}</p>
          {turn.footer}
          {turn.role === "assistant" && (typeof turn.confidence === "number" || turn.onFeedback) && (
            <div className="mt-2 flex items-center gap-2 border-t border-edge pt-2">
              {typeof turn.confidence === "number" && turn.confidence < LOW_CONFIDENCE_THRESHOLD && lowConfidenceLabel && (
                <Badge variant="warning">{lowConfidenceLabel}</Badge>
              )}
              {turn.onFeedback && (
                <div className="ml-auto flex items-center gap-1">
                  <button
                    type="button"
                    aria-label={thumbsUpLabel}
                    aria-pressed={turn.feedbackGiven === "up"}
                    disabled={!!turn.feedbackGiven}
                    onClick={() => turn.onFeedback?.("up")}
                    className={`rounded p-1 transition-colors duration-fast disabled:cursor-default ${
                      turn.feedbackGiven === "up" ? "text-accent" : "text-ink-3 hover:text-ink disabled:opacity-40"
                    }`}
                  >
                    <ThumbIcon />
                  </button>
                  <button
                    type="button"
                    aria-label={thumbsDownLabel}
                    aria-pressed={turn.feedbackGiven === "down"}
                    disabled={!!turn.feedbackGiven}
                    onClick={() => turn.onFeedback?.("down")}
                    className={`rounded p-1 transition-colors duration-fast disabled:cursor-default ${
                      turn.feedbackGiven === "down" ? "text-danger" : "text-ink-3 hover:text-ink disabled:opacity-40"
                    }`}
                  >
                    <ThumbIcon down />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
      {sending && (
        <div
          role="status"
          aria-label={thinkingLabel}
          className="glass-surface flex w-fit items-center gap-1 self-start rounded-ds-lg rounded-bl-sm border border-edge px-4 py-3"
        >
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3 [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3" />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
