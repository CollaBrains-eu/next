import { useLayoutEffect, useRef, type ChangeEvent, type KeyboardEvent } from "react";

const MAX_HEIGHT_PX = 160;

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}

/**
 * Auto-resizing textarea shared by Chat.tsx and Assistant.tsx. Enter submits
 * the enclosing form (via the native form.requestSubmit(), not an onSubmit
 * prop -- this component must be rendered inside a <form>); Shift+Enter
 * inserts a newline instead.
 */
export function ChatInput({ value, onChange, placeholder, disabled }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keyed on `value` (not just run inside handleChange) so the resize also
  // applies on the initial render and when the value changes externally --
  // e.g. Chat.tsx/Assistant.tsx calling setInput("") after submit, which
  // updates the controlled value without ever firing onChange.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  function handleChange(e: ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      rows={1}
      style={{ maxHeight: `${MAX_HEIGHT_PX}px` }}
      className="w-full resize-none overflow-y-auto rounded-ds-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
    />
  );
}
