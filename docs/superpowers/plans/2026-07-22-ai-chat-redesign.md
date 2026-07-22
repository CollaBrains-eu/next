# AI Chat Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the design-token visual language from sub-project 1
(`glass-surface`, `bg-gradient-brand`, `rounded-ds-*`) to `/chat` and
`/assistant`, with a full-height layout and an auto-resizing textarea input,
replacing the current 420px-capped widget-like box and single-line input.

**Architecture:** Frontend-only, no backend/API changes. `ChatLog.tsx` gets a
design-token restyle and drops its own scroll cap in favor of filling its flex
parent. A new shared `ChatInput.tsx` component (auto-resizing textarea,
Enter-submits/Shift+Enter-newlines via the browser's native `form.requestSubmit()`)
replaces the single-line `<input>` in both pages. `Chat.tsx`/`Assistant.tsx` get
their root layout restructured to `flex h-full flex-col` so the message log
becomes the scrolling region and the input stays pinned at the bottom.

**Tech Stack:** React + TypeScript + Vitest/Testing Library, existing design
tokens from `tailwind.config.js`/`tokens.css` (sub-project 1).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-22-ai-chat-redesign-design.md`.
- No backend changes anywhere in this plan — `chat()`/`askManager()` API calls stay
  exactly as they are.
- No new i18n keys needed — `chat.inputPlaceholder`/`assistant.inputPlaceholder`
  and all other copy already exist in `en.json`/`nl.json`/`de.json`.
- `vite build` is the real frontend gate, not `tsc -b` (106 pre-existing, unrelated
  errors, documented in sub-project 1's plan). `eslint` is not installed — skip
  linting.
- Live-browser verification is required for the full-height layout change (Task 3)
  — flexbox height propagation through `Layout.tsx`'s `<main class="flex-1
  overflow-y-auto">` wrapper is exactly the kind of thing that looked right on
  paper but broke in the browser during sub-project 1 (the header-clipping bug).
  If `h-full` doesn't resolve to a real height, fall back to an explicit
  viewport-relative height and document the finding in this plan.
- Frontend deploy requires an explicit `docker compose exec web sh -c 'cd
  /app/apps/web && npx vite build'` on the server — `docker compose up -d web`
  alone does not rebuild it.

---

### Task 1: `ChatLog` design-token restyle

**Files:**
- Modify: `apps/web/src/components/ui/ChatLog.tsx`

**Interfaces:**
- No prop/behavior changes — `ChatTurnDisplay` and the `ChatLog` component's props
  are unchanged. This is a pure visual pass.

- [ ] **Step 1: Run the existing tests to confirm the baseline passes**

Run: `npx vitest run src/components/ui/ChatLog.test.tsx`
Expected: PASS (8 tests) — this is the regression baseline; no new test cases are
needed for a class-name-only change since none of the existing assertions inspect
styling.

- [ ] **Step 2: Restyle the bubbles and scroll container**

In `apps/web/src/components/ui/ChatLog.tsx`, change the turns container:

```tsx
  return (
    <div className="flex max-h-[420px] flex-col gap-3 overflow-y-auto">
```

to:

```tsx
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
```

Change the bubble className logic:

```tsx
          className={
            turn.role === "user"
              ? "self-end max-w-[80%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm text-white"
              : "max-w-[80%] rounded-2xl rounded-bl-sm border border-edge bg-surface px-4 py-2 text-sm text-ink"
          }
```

to:

```tsx
          className={
            turn.role === "user"
              ? "self-end max-w-[80%] rounded-ds-lg rounded-br-sm bg-gradient-brand px-4 py-2 text-sm text-white"
              : "glass-surface max-w-[80%] rounded-ds-lg rounded-bl-sm border border-edge px-4 py-2 text-sm text-ink"
          }
```

Change the "thinking" indicator's className:

```tsx
          className="flex w-fit items-center gap-1 self-start rounded-2xl rounded-bl-sm border border-edge bg-surface px-4 py-3"
```

to:

```tsx
          className="glass-surface flex w-fit items-center gap-1 self-start rounded-ds-lg rounded-bl-sm border border-edge px-4 py-3"
```

- [ ] **Step 3: Run the tests to verify they still pass**

Run: `npx vitest run src/components/ui/ChatLog.test.tsx`
Expected: PASS (8 tests), unchanged — confirms the restyle didn't alter any
observable behavior.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/ui/ChatLog.tsx
git commit -m "feat: apply design tokens to ChatLog bubbles"
```

---

### Task 2: Shared `ChatInput` component

**Files:**
- Create: `apps/web/src/components/ui/ChatInput.tsx`
- Test: `apps/web/src/components/ui/ChatInput.test.tsx`

**Interfaces:**
- Produces: `ChatInput({ value: string, onChange: (value: string) => void,
  placeholder: string, disabled?: boolean })` — consumed by Task 3's
  `Chat.tsx`/`Assistant.tsx`.
- Consumes: nothing new — relies on the browser's native
  `HTMLFormElement.requestSubmit()` (supported in this project's jsdom 25.0.1 test
  environment) to submit the enclosing `<form>` on Enter, so no `onSubmit` prop is
  needed — the component must be rendered inside a `<form>`.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/components/ui/ChatInput.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "./ChatInput";

function renderInForm(onSubmit: () => void, disabled = false) {
  return render(
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <ChatInput value="" onChange={() => {}} placeholder="Type…" disabled={disabled} />
    </form>
  );
}

describe("ChatInput", () => {
  it("renders the placeholder and current value", () => {
    render(
      <form>
        <ChatInput value="hello" onChange={() => {}} placeholder="Type…" />
      </form>
    );
    expect(screen.getByPlaceholderText("Type…")).toHaveValue("hello");
  });

  it("calls onChange with the new value when typed into", () => {
    const onChange = vi.fn();
    render(
      <form>
        <ChatInput value="" onChange={onChange} placeholder="Type…" />
      </form>
    );
    fireEvent.change(screen.getByPlaceholderText("Type…"), { target: { value: "hi" } });
    expect(onChange).toHaveBeenCalledWith("hi");
  });

  it("submits the enclosing form on Enter without Shift", () => {
    const onSubmit = vi.fn();
    renderInForm(onSubmit);
    fireEvent.keyDown(screen.getByPlaceholderText("Type…"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not submit the form on Shift+Enter", () => {
    const onSubmit = vi.fn();
    renderInForm(onSubmit);
    fireEvent.keyDown(screen.getByPlaceholderText("Type…"), { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables the textarea when disabled is true", () => {
    render(
      <form>
        <ChatInput value="" onChange={() => {}} placeholder="Type…" disabled />
      </form>
    );
    expect(screen.getByPlaceholderText("Type…")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/components/ui/ChatInput.test.tsx`
Expected: FAIL — `./ChatInput` does not exist yet.

- [ ] **Step 3: Implement `ChatInput.tsx`**

Create `apps/web/src/components/ui/ChatInput.tsx`:

```tsx
import { useRef, type ChangeEvent, type KeyboardEvent } from "react";

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

  function handleChange(e: ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
    }
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
      className="w-full resize-none rounded-ds-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
    />
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/ui/ChatInput.test.tsx`
Expected: PASS (5 tests). If the Enter-submits test fails with a "requestSubmit is
not a function" error rather than an assertion failure, that means this jsdom
version doesn't implement it — fall back to a controlled `<form>` re-submission
via a passed-down `formRef`/`onSubmit` prop instead, and update this step with
the actual working approach.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/ui/ChatInput.tsx apps/web/src/components/ui/ChatInput.test.tsx
git commit -m "feat: add shared auto-resizing ChatInput component"
```

---

### Task 3: Wire `ChatInput` + full-height layout into `Chat.tsx` and `Assistant.tsx`

**Files:**
- Modify: `apps/web/src/routes/Chat.tsx`
- Modify: `apps/web/src/routes/Assistant.tsx`
- Test: `apps/web/src/routes/Chat.test.tsx`, `apps/web/src/routes/Assistant.test.tsx`
  (existing tests should keep passing unchanged — placeholder-text-based queries
  work identically against a `<textarea>`)

**Interfaces:**
- Consumes: `ChatInput` (Task 2), `ChatLog`'s restyled scroll behavior (Task 1).

- [ ] **Step 1: Run the existing page tests to confirm the baseline passes**

Run: `npx vitest run src/routes/Chat.test.tsx src/routes/Assistant.test.tsx`
Expected: PASS (regression baseline before touching either page).

- [ ] **Step 2: Restructure `Chat.tsx`'s layout and swap in `ChatInput`**

Add the import:

```tsx
import { ChatInput } from "../components/ui/ChatInput";
```

Change the return statement:

```tsx
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("nav.aiChat")}</h1>

      <div className="flex flex-col gap-3">
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
```

to:

```tsx
  return (
    <div className="flex h-full flex-col gap-4">
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
```

- [ ] **Step 3: Restructure `Assistant.tsx`'s layout and swap in `ChatInput`**

Add the import:

```tsx
import { ChatInput } from "../components/ui/ChatInput";
```

Change the return statement:

```tsx
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("nav.assistant")}</h1>

      <div className="flex flex-col gap-3">
        <ChatLog turns={displayTurns} sending={sending} hint={t("assistant.hint")} thinkingLabel={t("common.thinking")} />
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("assistant.inputPlaceholder")}
          disabled={sending}
          className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          {t("common.send")}
        </Button>
      </form>
    </div>
  );
```

to:

```tsx
  return (
    <div className="flex h-full flex-col gap-4">
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
```

- [ ] **Step 4: Run tests to verify they still pass**

Run: `npx vitest run src/routes/Chat.test.tsx src/routes/Assistant.test.tsx`
Expected: PASS, unchanged test count — `getByPlaceholderText`/`fireEvent.change`
work identically against the new `ChatInput`-rendered `<textarea>`.

- [ ] **Step 5: Live-browser verification**

Temporarily override `useAuth()` in `apps/web/src/lib/auth.tsx` to return a fixed
fake user (per this session's established technique), start the dev server,
screenshot `/chat` and `/assistant` at desktop and mobile widths. Confirm:
- The message log fills available vertical space and scrolls internally once it
  overflows, rather than growing the whole page.
- The input area stays pinned at the bottom of the viewport.
- If `h-full` does not propagate a real height through `Layout.tsx`'s `<main>`
  (the header-clipping-style risk flagged in Global Constraints), replace `h-full`
  with an explicit height (e.g. a `calc()` accounting for `<main>`'s padding) and
  re-verify.

Revert the `useAuth()` override via `git checkout -- apps/web/src/lib/auth.tsx`
before continuing — never commit it.

- [ ] **Step 6: Run the full frontend test suite and build**

Run: `npx vitest run` then `npx vite build`
Expected: all tests PASS, build succeeds with no new errors.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/Chat.tsx apps/web/src/routes/Assistant.tsx
git commit -m "feat: full-height chat layout with auto-resizing input"
```

---

## Deployment

1. Push to `main`.
2. On the server: `git pull` (check for and discard any byte-identical leftover
   rsync artifacts first, same as prior sub-projects).
3. Rebuild the frontend: `docker compose exec web sh -c 'cd /app/apps/web && npx
   vite build'`.
4. No backend restart needed — no backend changes in this plan.
5. Verify live: open `/chat` and `/assistant` in the browser, send a message on
   each, confirm the new bubble styling and full-height scroll behavior.
