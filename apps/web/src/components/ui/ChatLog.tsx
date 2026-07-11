import { useEffect, useRef, type ReactNode } from "react";

export interface ChatTurnDisplay {
  role: "user" | "assistant";
  content: string;
  footer?: ReactNode;
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
}: {
  turns: ChatTurnDisplay[];
  sending: boolean;
  hint?: string;
  thinkingLabel: string;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // optional chaining on the call itself, not just the ref: jsdom (this
    // project's test environment) doesn't implement scrollIntoView at all
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, sending]);

  if (turns.length === 0) {
    return hint ? <p className="text-sm text-ink-2">{hint}</p> : null;
  }

  return (
    <div className="flex max-h-[420px] flex-col gap-3 overflow-y-auto">
      {turns.map((turn, i) => (
        <div
          key={i}
          className={
            turn.role === "user"
              ? "self-end max-w-[80%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm text-white"
              : "max-w-[80%] rounded-2xl rounded-bl-sm border border-edge bg-surface px-4 py-2 text-sm text-ink"
          }
        >
          <p className="whitespace-pre-wrap">{turn.content}</p>
          {turn.footer}
        </div>
      ))}
      {sending && (
        <div
          role="status"
          aria-label={thinkingLabel}
          className="flex w-fit items-center gap-1 self-start rounded-2xl rounded-bl-sm border border-edge bg-surface px-4 py-3"
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
