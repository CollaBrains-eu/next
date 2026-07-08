# Phase 20d5: Settings & Assistant Page Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `Settings.tsx` and `Assistant.tsx` to the violet design system, completing Phase 20's page-by-page rollout. This is the final page cluster — after this phase, all 9 real pages (Documents, Cases/Vehicles, Entities/EntityGraph, Chat/Legal/Tasks, Settings/Assistant) match the validated design language.

**Architecture:** Data-fetching logic is untouched. `Assistant.tsx` mirrors `Chat.tsx`'s migration exactly (same message-bubble/loading-bar pattern, different backend endpoint) since both are AI conversation UIs. `Settings.tsx` gets a token-class pass plus `Button` for Save.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (violet token theme), Vitest 3, @testing-library/react, react-router-dom.

## Global Constraints

- Do not modify `apps/web/src/lib/api.ts` — only real, existing exports may be used (`ApiError`, `getPreferences`, `setPreferences`, `PreferencesOut`, `askManager`, `AskResponse`).
- `Settings.tsx`'s language `<select>` stays hand-styled (token classes) rather than the `Select` primitive — `LANGUAGE_OPTIONS` has distinct value/label pairs (`{value: "", label: "No preference"}`), which doesn't fit `Select`'s `options: string[]` (value===label) API. Same deliberate-deviation precedent as 20d2 (CaseDetail) and 20d3 (Entities).
- `Assistant.tsx` wires up `useLoadingBar()` around `askManager()`, matching Chat.tsx's Phase 20d4 pattern — the Assistant is another AI round-trip that can take significant time.
- Verify each task with `npx vite build` (from `apps/web`) + `pnpm test` (not full `pnpm build` — pre-existing `apps/mobile`/`apps/web` `@types/react` hoisting conflict, documented in PR #28, remains out of scope).
- Branch this plan's implementation off `phase-20d5-plan-settings-assistant-migration` (this plan's own branch), which itself sits on `phase-20d4-chat-legal-tasks-migration` — nothing is merged to `main` yet.
- Commit after each task. Push and open a PR against `main` at the end (do not merge).

---

### Task 1: Migrate Settings.tsx

**Files:**
- Modify: `apps/web/src/routes/Settings.tsx`
- Test: `apps/web/src/routes/Settings.test.tsx` (new)

**Interfaces:**
- Consumes: `Button` (`import { Button } from "../components/ui/Button"`), `Card` (unchanged), `ApiError`/`getPreferences`/`setPreferences` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Settings.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getPreferences: vi.fn(),
    setPreferences: vi.fn(),
  };
});

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getPreferences).mockResolvedValue({ preferred_language: "Nederlands" });
    vi.mocked(api.setPreferences).mockResolvedValue({ preferred_language: "English" });
  });

  it("loads and selects the saved preferred language", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
  });

  it("saves the selected language and shows a confirmation", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.change(screen.getByLabelText("Preferred language"), { target: { value: "English" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.setPreferences).toHaveBeenCalledWith("English"));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("shows an error message when saving fails", async () => {
    vi.mocked(api.setPreferences).mockRejectedValue(new api.ApiError(500, "Save boom"));
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Save boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Settings.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Settings.tsx**

```tsx
import { useEffect, useState } from "react";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { ApiError, getPreferences, setPreferences } from "../lib/api";

const LANGUAGE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "English", label: "English" },
  { value: "Nederlands", label: "Nederlands" },
  { value: "Deutsch", label: "Deutsch" },
];

export default function Settings() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPreferences()
      .then((prefs) => setLanguage(prefs.preferred_language ?? ""))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load preferences"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences(language || null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">Settings</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium text-ink" htmlFor="preferred-language">
            Preferred language
          </label>
          <p className="text-xs text-ink-3">Used by AI Chat to respond in your preferred language.</p>
        </div>
        {loading ? (
          <p className="text-sm text-ink-3">Loading…</p>
        ) : (
          <select
            id="preferred-language"
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              setSaved(false);
            }}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">Saved.</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          Save
        </Button>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Settings.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx
git commit -m "feat(web): migrate Settings page to violet design system"
```

---

### Task 2: Migrate Assistant.tsx

**Files:**
- Modify: `apps/web/src/routes/Assistant.tsx`
- Test: `apps/web/src/routes/Assistant.test.tsx` (new)

**Interfaces:**
- Consumes: `Button`, `useLoadingBar` (same imports as Chat.tsx, Phase 20d4), `ApiError`/`askManager`/`AskResponse` from `../lib/api` (unchanged). Test must wrap in `LoadingBarProvider` since `useLoadingBar` throws outside it.
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Assistant.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Assistant from "./Assistant";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    askManager: vi.fn(),
  };
});

function renderPage() {
  return render(
    <LoadingBarProvider>
      <Assistant />
    </LoadingBarProvider>
  );
}

describe("Assistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.askManager).mockResolvedValue({ answer: "I created the case.", tool_called: "create_case" });
  });

  it("shows the hint text before any messages are sent", () => {
    renderPage();
    expect(screen.getByText(/Ask the assistant to do something/)).toBeInTheDocument();
  });

  it("sends a message and renders the assistant reply with the tool it called", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask the assistant…"), { target: { value: "Create a case for Smith" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("I created the case.")).toBeInTheDocument();
    expect(screen.getByText("via: create_case")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.askManager).mockRejectedValue(new api.ApiError(500, "Assistant boom"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask the assistant…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Assistant boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Assistant.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Assistant.tsx**

```tsx
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Assistant.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Assistant.tsx apps/web/src/routes/Assistant.test.tsx
git commit -m "feat(web): migrate Assistant page to violet design system, wire up loading bar"
```

---

### Task 3: Full-suite verification and manual browser check

- [ ] **Step 1: Run the full test suite**

Run: `cd /opt/collabrains/apps/web && pnpm test`
Expected: all tests pass (previous 152 + this plan's 6 new tests = 158).

- [ ] **Step 2: Production build sanity check**

Run: `cd /opt/collabrains/apps/web && npx vite build`
Expected: build succeeds with no errors.

- [ ] **Step 3: Manual verification against real production data**

Tunnel to the live `web`/`api` containers exactly as done in prior phases (check `lsof -i :PORT` first for local collisions; widen `allow_origins` in `services/api/src/api/main.py` temporarily if needed, revert immediately after). Using Playwright, visit `/settings` and confirm the real saved language preference loads and a change persists via a real `Save` click; visit `/assistant` and send one real message, confirming the loading bar runs during the request and a real tool-calling response renders (accepting that, per Chat.tsx's 20d4 verification, this may take up to ~70s against the real Ollama backend — use the same Monitor-based non-polling wait pattern rather than sleeping in a loop).

- [ ] **Step 4: Revert any temporary CORS change and restart the api container if it was modified**

```bash
cd /opt/collabrains && git diff services/api/src/api/main.py
# if changed, revert:
git checkout services/api/src/api/main.py
docker compose restart api
```
