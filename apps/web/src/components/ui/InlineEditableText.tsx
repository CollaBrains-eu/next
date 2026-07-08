import { useRef, useState } from "react";

export function InlineEditableText({ value, onSave }: { value: string; onSave: (newValue: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [displayValue, setDisplayValue] = useState(value);
  const committedRef = useRef(false);

  function startEditing() {
    setDraft(displayValue);
    committedRef.current = false;
    setEditing(true);
  }

  function commit() {
    if (committedRef.current) return;
    committedRef.current = true;
    const trimmed = draft.trim();
    if (trimmed) {
      setDisplayValue(trimmed);
      onSave(trimmed);
    }
    setEditing(false);
  }

  function cancel() {
    committedRef.current = true;
    setEditing(false);
  }

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span>{displayValue}</span>
        <button
          aria-label="Edit"
          onClick={startEditing}
          className="rounded-md p-0.5 text-ink-3 transition-colors duration-fast hover:bg-hover hover:text-accent"
        >
          ✎
        </button>
      </span>
    );
  }

  return (
    <input
      autoFocus
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        } else if (event.key === "Escape") {
          cancel();
        }
      }}
      className="rounded-lg border border-accent bg-surface px-2 py-1 text-sm text-ink outline-none ring-2 ring-accent-soft"
    />
  );
}
