# Phase 7 Mobile App (React Native / Expo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-mostly companion mobile app (React Native / Expo) covering document browsing/search, AI chat, tasks, and the entity graph, against the existing CollaBrains backend.

**Architecture:** Expo + Expo Router (file-based screens) + TypeScript, mirroring `apps/web`'s `lib/api.ts`/`lib/auth.tsx` shape. Talks directly to `https://v78281.1blu.de` (no dev/prod URL split needed). JWT stored in `expo-secure-store`. No caching library — plain `useState`/`useEffect` + pull-to-refresh, matching the web app.

**Tech Stack:** Expo SDK (latest stable), React Native, TypeScript, Expo Router, `expo-secure-store`, `react-native-svg`, `vitest` (for `lib/api.ts` unit tests only).

## Global Constraints

- All work happens on the remote server at `/opt/collabrains` via SSH (`root@195.90.216.230`) — nothing is created or run locally. Use the established safe file-transfer pattern for any file with backticks/quotes: write locally to a scratch path, then `cat > remote/path` via SSH stdin, never inline heredocs through nested shells.
- New files go under `apps/mobile/`. Do not modify `apps/web` except where explicitly noted (there is no such case in this plan — mobile is fully additive).
- Backend base URL is `https://v78281.1blu.de` (Phase 6a). No environment-variable indirection for it — hardcode it in `src/lib/api.ts`.
- Auth token storage uses `expo-secure-store`'s async API (`getItemAsync`/`setItemAsync`/`deleteItemAsync`), not `localStorage`.
- Match `apps/web`'s existing code style: no comments except where a non-obvious constraint justifies one, typed API responses via hand-written interfaces (no codegen).
- Every screen owns its own loading/error state via `useState`; no global state library.
- Verification for UI work is **live testing against the real backend** (build the app via Expo, walk through actual screens), not unit tests — same discipline the web app used throughout this project, since there's no mobile equivalent of the Playwright MCP tool available in this environment. `lib/api.ts` gets real `vitest` unit tests (ported from web's suite) since that logic is genuinely unit-testable.
- After finishing all tasks: update root `README.md`'s status/phase list and write `docs/adr/0016-phase7-mobile-app-foundation.md`'s implementation into a fresh commit (the ADR itself is already committed — this plan implements it).

---

### Task 1: Scaffold the Expo project

**Files:**
- Create: `apps/mobile/package.json`
- Create: `apps/mobile/app.json`
- Create: `apps/mobile/tsconfig.json`
- Create: `apps/mobile/babel.config.js`
- Create: `apps/mobile/app/_layout.tsx`
- Create: `apps/mobile/app/index.tsx` (placeholder, replaced in Task 4)
- Modify: `.gitignore` (add `apps/mobile/node_modules/`, `apps/mobile/.expo/` if not already covered by a blanket `node_modules/`/pattern — check first)

**Interfaces:**
- Produces: a runnable blank Expo app (`npx expo start` succeeds, root route renders placeholder text).

- [ ] **Step 1: Check the existing `.gitignore` covers Expo's build artifacts**

```bash
ssh root@195.90.216.230 "grep -n 'node_modules\|\.expo' /opt/collabrains/.gitignore"
```

Expected: `node_modules/` already present (confirmed present from Phase 5a — it's a blanket pattern covering any `node_modules` anywhere in the tree). If `.expo/` is not present, add it:

```bash
ssh root@195.90.216.230 "echo '.expo/' >> /opt/collabrains/.gitignore"
```

- [ ] **Step 2: Create `apps/mobile/package.json`**

```json
{
  "name": "mobile",
  "version": "1.0.0",
  "main": "expo-router/entry",
  "private": true,
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "test": "vitest run"
  },
  "dependencies": {
    "expo": "~52.0.0",
    "expo-router": "~4.0.0",
    "expo-secure-store": "~14.0.0",
    "expo-status-bar": "~2.0.0",
    "react": "18.3.1",
    "react-native": "0.76.5",
    "react-native-safe-area-context": "4.12.0",
    "react-native-screens": "~4.4.0",
    "react-native-svg": "15.8.0"
  },
  "devDependencies": {
    "@babel/core": "^7.25.0",
    "@types/react": "~18.3.12",
    "typescript": "~5.3.3",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 3: Create `apps/mobile/app.json`**

```json
{
  "expo": {
    "name": "CollaBrains",
    "slug": "collabrains-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "userInterfaceStyle": "light",
    "scheme": "collabrains",
    "plugins": ["expo-router"],
    "ios": {
      "supportsTablet": false,
      "bundleIdentifier": "eu.collabrains.mobile"
    },
    "android": {
      "package": "eu.collabrains.mobile"
    }
  }
}
```

- [ ] **Step 4: Create `apps/mobile/tsconfig.json`**

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"]
}
```

- [ ] **Step 5: Create `apps/mobile/babel.config.js`**

```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
  };
};
```

- [ ] **Step 6: Create a placeholder root layout and index route**

`apps/mobile/app/_layout.tsx`:

```tsx
import { Stack } from "expo-router";

export default function RootLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
```

`apps/mobile/app/index.tsx`:

```tsx
import { Text, View } from "react-native";

export default function Index() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <Text>CollaBrains Mobile</Text>
    </View>
  );
}
```

- [ ] **Step 7: Install dependencies and verify the app boots**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npm install"
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx expo start --non-interactive --no-dev &" 
# Check it starts without error, then kill it -- full interactive verification (scanning
# the QR code with a real device) happens in Task 11, not here. This step only confirms
# the scaffold itself is not broken (dependency resolution succeeds, Metro bundler starts).
```

Expected: Metro bundler starts and prints a QR code / dev server URL without throwing.

- [ ] **Step 8: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/ .gitignore && git commit -m 'Phase 7: scaffold Expo mobile app'"
```

---

### Task 2: Port the API client with tests

**Files:**
- Create: `apps/mobile/src/lib/api.ts`
- Create: `apps/mobile/src/lib/api.test.ts`
- Create: `apps/mobile/vitest.config.ts`

**Interfaces:**
- Consumes: nothing (no dependency on other mobile tasks).
- Produces: `request<T>()`, `ApiError`, `getToken/setToken/clearToken` (all async, returning `Promise`), `login`, `fetchMe`, `listDocuments`, `getDocument`, `search`, `chat`, `listTasks`, `updateTaskStatus`, `listEntities`, `getEntityGraph`, and all associated TypeScript interfaces (`UserOut`, `DocumentOut`, `DocumentDetailOut`, `SearchResult`, `ChatTurn`, `ChatResponse`, `Citation`, `TaskOut`, `EntityOut`, `GraphNode`, `GraphEdge`, `EntityGraphOut`) — same names and shapes as `apps/web/src/lib/api.ts`, consumed by every later screen task.

- [ ] **Step 1: Write the failing tests first**

`apps/mobile/src/lib/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, clearToken, login, request, setToken } from "./api";

describe("api request()", () => {
  beforeEach(async () => {
    await clearToken();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults to application/json when the caller sets no Content-Type", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await request("/documents", { method: "POST", body: JSON.stringify({ title: "x" }) });

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).get("Content-Type")).toBe("application/json");
  });

  it("does not override a Content-Type the caller explicitly set", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ access_token: "tok", token_type: "bearer" }), { status: 200 }),
    );

    await login("admin1", "hunter2");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).get("Content-Type")).toBe("application/x-www-form-urlencoded");
  });

  it("attaches a bearer token when one is stored", async () => {
    await setToken("secret-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("{}", { status: 200 }));

    await request("/auth/me");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer secret-token");
  });

  it("throws ApiError with the parsed detail message on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ detail: "not linked" }), { status: 403, statusText: "Forbidden" }),
    );

    await expect(request("/chat")).rejects.toMatchObject(new ApiError(403, "not linked"));
  });
});
```

- [ ] **Step 2: Create `apps/mobile/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
  },
});
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx vitest run"
```

Expected: FAIL — `Cannot find module './api'` (file doesn't exist yet).

- [ ] **Step 4: Implement `apps/mobile/src/lib/api.ts`**

```ts
import * as SecureStore from "expo-secure-store";

const API_URL = "https://v78281.1blu.de";
const TOKEN_KEY = "collabrains_token";

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface UserOut {
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
}

export async function login(username: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username, password });
  const result = await request<{ access_token: string; token_type: string }>("/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  return result.access_token;
}

export function fetchMe(): Promise<UserOut> {
  return request<UserOut>("/auth/me");
}

export interface DocumentOut {
  id: string;
  title: string;
  filename: string;
  mime_type: string;
  status: string;
  error: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DocumentDetailOut extends DocumentOut {
  ocr_text: string | null;
  chunk_count: number;
  summary: string | null;
}

export function listDocuments(): Promise<DocumentOut[]> {
  return request<DocumentOut[]>("/documents");
}

export function getDocument(id: string): Promise<DocumentDetailOut> {
  return request<DocumentDetailOut>(`/documents/${id}`);
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
}

export function search(query: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
}

export interface Citation {
  marker: number;
  document_id: string;
  document_title: string;
  chunk_id: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
}

export function chat(message: string, history: ChatTurn[]): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export interface TaskOut {
  id: string;
  document_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  assignee: string | null;
  status: string;
  source: string;
  created_at: string;
}

export function listTasks(statusFilter?: string): Promise<TaskOut[]> {
  const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
  return request<TaskOut[]>(`/tasks${query}`);
}

export function updateTaskStatus(id: string, status: "open" | "done"): Promise<TaskOut> {
  return request<TaskOut>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export interface EntityOut {
  id: string;
  name: string;
  entity_type: string;
  created_at: string;
}

export function listEntities(q?: string, entityType?: string): Promise<EntityOut[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (entityType) params.set("entity_type", entityType);
  const query = params.toString();
  return request<EntityOut[]>(`/entities${query ? `?${query}` : ""}`);
}

export interface GraphNode {
  id: string;
  name: string;
  entity_type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
  document_id: string | null;
}

export interface EntityGraphOut {
  center: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function getEntityGraph(id: string): Promise<EntityGraphOut> {
  return request<EntityGraphOut>(`/entities/${id}/graph`);
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx vitest run"
```

Expected: PASS — 4/4 tests.

- [ ] **Step 6: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/src/lib/api.ts apps/mobile/src/lib/api.test.ts apps/mobile/vitest.config.ts && git commit -m 'Phase 7: port API client with SecureStore-backed auth'"
```

---

### Task 3: Auth context and login screen

**Files:**
- Create: `apps/mobile/src/lib/auth.tsx`
- Create: `apps/mobile/app/login.tsx`
- Modify: `apps/mobile/app/_layout.tsx` (wrap in `AuthProvider`)

**Interfaces:**
- Consumes: `login`, `fetchMe`, `clearToken`, `setToken`, `ApiError`, `UserOut` from Task 2's `src/lib/api.ts`.
- Produces: `AuthProvider`, `useAuth()` returning `{ user: UserOut | null, loading: boolean, login: (username, password) => Promise<void>, logout: () => Promise<void> }` — consumed by every screen task to guard routes and read the current user.

- [ ] **Step 1: Implement `apps/mobile/src/lib/auth.tsx`**

```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, clearToken, fetchMe, login as apiLogin, setToken, type UserOut } from "./api";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await fetchMe());
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        await clearToken();
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (username: string, password: string) => {
      const token = await apiLogin(username, password);
      await setToken(token);
      await refreshUser();
    },
    [refreshUser],
  );

  const logout = useCallback(async () => {
    await clearToken();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Create `apps/mobile/app/login.tsx`**

```tsx
import { useState } from "react";
import { router } from "expo-router";
import { ActivityIndicator, Button, StyleSheet, Text, TextInput, View } from "react-native";
import { ApiError } from "../src/lib/api";
import { useAuth } from "../src/lib/auth";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>CollaBrains</Text>
      <TextInput
        style={styles.input}
        placeholder="Username"
        value={username}
        onChangeText={setUsername}
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      {error && <Text style={styles.error}>{error}</Text>}
      {submitting ? <ActivityIndicator /> : <Button title="Sign in" onPress={handleSubmit} />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 24, fontWeight: "600", marginBottom: 24, textAlign: "center" },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  error: { color: "#dc2626" },
});
```

- [ ] **Step 3: Wrap the root layout in `AuthProvider` and add a route guard**

`apps/mobile/app/_layout.tsx`:

```tsx
import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect } from "react";
import { AuthProvider, useAuth } from "../src/lib/auth";

function Guard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    const onLogin = segments[0] === "login";
    if (!user && !onLogin) router.replace("/login");
    if (user && onLogin) router.replace("/");
  }, [user, loading, segments, router]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <Guard>
        <Stack screenOptions={{ headerShown: false }} />
      </Guard>
    </AuthProvider>
  );
}
```

- [ ] **Step 4: Verify the module resolves and TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/src/lib/auth.tsx apps/mobile/app/login.tsx apps/mobile/app/_layout.tsx && git commit -m 'Phase 7: auth context, login screen, route guard'"
```

---

### Task 4: Tab navigator shell

**Files:**
- Create: `apps/mobile/app/(tabs)/_layout.tsx`
- Modify: `apps/mobile/app/index.tsx` (delete — replaced by `(tabs)/index.tsx` in Task 5)

**Interfaces:**
- Consumes: `useAuth` from Task 3.
- Produces: the `(tabs)` route group with 4 tab slots (`index`, `chat`, `tasks`, `entities/index`) ready for Tasks 5-9 to fill in. This task creates the navigator shell only — Task 5-9 create the actual screen content.

- [ ] **Step 1: Remove the placeholder root index route**

```bash
ssh root@195.90.216.230 "rm /opt/collabrains/apps/mobile/app/index.tsx"
```

- [ ] **Step 2: Create the tab layout**

`apps/mobile/app/(tabs)/_layout.tsx`:

```tsx
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs>
      <Tabs.Screen name="index" options={{ title: "Documents" }} />
      <Tabs.Screen name="chat" options={{ title: "Chat" }} />
      <Tabs.Screen name="tasks" options={{ title: "Tasks" }} />
      <Tabs.Screen name="entities/index" options={{ title: "Entities" }} />
    </Tabs>
  );
}
```

- [ ] **Step 3: Add minimal placeholder screens so the navigator has something to render**

(These get replaced with real content in Tasks 5-9; this step exists only so Task 4's verification step has something to check.)

`apps/mobile/app/(tabs)/index.tsx`:
```tsx
import { Text, View } from "react-native";
export default function DocumentsPlaceholder() {
  return <View style={{ flex: 1 }}><Text>Documents</Text></View>;
}
```

`apps/mobile/app/(tabs)/chat.tsx`:
```tsx
import { Text, View } from "react-native";
export default function ChatPlaceholder() {
  return <View style={{ flex: 1 }}><Text>Chat</Text></View>;
}
```

`apps/mobile/app/(tabs)/tasks.tsx`:
```tsx
import { Text, View } from "react-native";
export default function TasksPlaceholder() {
  return <View style={{ flex: 1 }}><Text>Tasks</Text></View>;
}
```

`apps/mobile/app/(tabs)/entities/index.tsx`:
```tsx
import { Text, View } from "react-native";
export default function EntitiesPlaceholder() {
  return <View style={{ flex: 1 }}><Text>Entities</Text></View>;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

Expected: no errors.

- [ ] **Step 5: Verify the tab bar actually renders and routes correctly (tsc alone won't catch a wrong route name)**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx expo start --tunnel"
```

Connect with Expo Go (see Task 11 Step 2 for the tunnel-mode rationale) and confirm: all 4 tabs (Documents, Chat, Tasks, Entities) appear in the tab bar, and tapping "Entities" actually navigates to the `(tabs)/entities/index.tsx` placeholder rather than erroring or landing on the wrong screen. **This is the specific thing to watch for**: Expo Router's `Tabs.Screen name="entities/index"` may need to be `name="entities"` instead, depending on the installed Expo Router version's handling of a nested folder's index route inside a tab group — if the "Entities" tab doesn't route correctly, try `name="entities"` first. Stop the dev server (Ctrl+C) once confirmed; this is a one-time structural check, not the full walkthrough (that's Task 11).

- [ ] **Step 6: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/app/ && git commit -m 'Phase 7: tab navigator shell with placeholder screens'"
```

---

### Task 5: Document list screen

**Files:**
- Modify: `apps/mobile/app/(tabs)/index.tsx` (replace placeholder)

**Interfaces:**
- Consumes: `listDocuments`, `search`, `DocumentOut`, `SearchResult`, `ApiError` from Task 2.
- Produces: nothing new consumed elsewhere (leaf screen), but establishes the pull-to-refresh + status-badge pattern reused conceptually by Tasks 8-9.

- [ ] **Step 1: Implement the document list with search and pull-to-refresh**

`apps/mobile/app/(tabs)/index.tsx`:

```tsx
import { useCallback, useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { listDocuments, search as searchApi, type DocumentOut, type SearchResult } from "../../src/lib/api";

const STATUS_COLORS: Record<string, string> = {
  ready: "#16a34a",
  pending: "#64748b",
  ocr_processing: "#d97706",
  embedding: "#d97706",
  failed: "#dc2626",
};

export default function Documents() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setDocuments(await listDocuments());
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSearch(text: string) {
    setQuery(text);
    if (!text.trim()) {
      setResults(null);
      return;
    }
    setResults(await searchApi(text.trim()));
  }

  const items = results !== null
    ? results.map((r) => ({ id: r.chunk_id, title: r.document_title, subtitle: r.content, docId: r.document_id, status: null }))
    : documents.map((d) => ({ id: d.id, title: d.title, subtitle: new Date(d.created_at).toLocaleString(), docId: d.id, status: d.status }));

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.search}
        placeholder="Search documents..."
        value={query}
        onChangeText={handleSearch}
      />
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => router.push(`/documents/${item.docId}`)}>
            <Text style={styles.rowTitle}>{item.title}</Text>
            <Text style={styles.rowSubtitle} numberOfLines={2}>{item.subtitle}</Text>
            {item.status && (
              <Text style={[styles.badge, { color: STATUS_COLORS[item.status] ?? "#64748b" }]}>{item.status}</Text>
            )}
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No documents yet.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  search: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 12 },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  rowTitle: { fontSize: 15, fontWeight: "500" },
  rowSubtitle: { fontSize: 13, color: "#64748b", marginTop: 2 },
  badge: { fontSize: 12, marginTop: 4 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

Expected: no errors (note: `documents/[id]` doesn't exist until Task 6, so `router.push` there is fine at the type level since Expo Router's typed routes aren't enforced until the route file exists and the app is built — this compiles regardless).

- [ ] **Step 3: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/app/\(tabs\)/index.tsx && git commit -m 'Phase 7: document list screen with search and pull-to-refresh'"
```

---

### Task 6: Document detail screen

**Files:**
- Create: `apps/mobile/app/documents/[id].tsx`

**Interfaces:**
- Consumes: `getDocument`, `DocumentDetailOut`, `ApiError` from Task 2.

- [ ] **Step 1: Implement the detail screen**

`apps/mobile/app/documents/[id].tsx`:

```tsx
import { useEffect, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { ApiError, getDocument, type DocumentDetailOut } from "../../src/lib/api";

export default function DocumentDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load document"));
  }, [id]);

  if (error) return <View style={styles.container}><Text style={styles.error}>{error}</Text></View>;
  if (!doc) return <View style={styles.container}><ActivityIndicator /></View>;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{doc.title}</Text>
      <Text style={styles.meta}>{doc.mime_type} · {doc.status} · {doc.chunk_count} chunk(s)</Text>
      {doc.summary && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary</Text>
          <Text>{doc.summary}</Text>
        </View>
      )}
      {doc.ocr_text && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Extracted text</Text>
          <Text>{doc.ocr_text}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  content: { gap: 12 },
  title: { fontSize: 20, fontWeight: "600" },
  meta: { fontSize: 13, color: "#64748b" },
  section: { marginTop: 8, gap: 4 },
  sectionTitle: { fontSize: 14, fontWeight: "600", color: "#64748b" },
  error: { color: "#dc2626" },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

- [ ] **Step 3: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/app/documents/ && git commit -m 'Phase 7: document detail screen'"
```

---

### Task 7: Chat screen

**Files:**
- Modify: `apps/mobile/app/(tabs)/chat.tsx` (replace placeholder)

**Interfaces:**
- Consumes: `chat`, `ChatTurn`, `Citation`, `ApiError` from Task 2.

- [ ] **Step 1: Implement the chat screen**

`apps/mobile/app/(tabs)/chat.tsx`:

```tsx
import { useState } from "react";
import { router } from "expo-router";
import { ActivityIndicator, FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { ApiError, chat, type ChatTurn, type Citation } from "../../src/lib/api";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
}

export default function Chat() {
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
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
    <View style={styles.container}>
      <FlatList
        data={turns}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === "user" ? styles.userBubble : styles.assistantBubble]}>
            <Text style={item.role === "user" ? styles.userText : styles.assistantText}>{item.content}</Text>
            {item.citations?.map((c) => (
              <TouchableOpacity key={c.chunk_id} onPress={() => router.push(`/documents/${c.document_id}`)}>
                <Text style={styles.citation}>[{c.marker}] {c.document_title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>Ask a question about your documents.</Text>}
      />
      {sending && <ActivityIndicator style={styles.spinner} />}
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          placeholder="Ask a question..."
          value={input}
          onChangeText={setInput}
          editable={!sending}
        />
        <TouchableOpacity onPress={handleSend} disabled={sending || !input.trim()}>
          <Text style={styles.send}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  list: { gap: 8 },
  bubble: { padding: 10, borderRadius: 8, maxWidth: "85%" },
  userBubble: { backgroundColor: "#0f172a", alignSelf: "flex-end" },
  assistantBubble: { backgroundColor: "#f1f5f9", alignSelf: "flex-start" },
  userText: { color: "#fff" },
  assistantText: { color: "#0f172a" },
  citation: { fontSize: 12, color: "#2563eb", marginTop: 4 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
  spinner: { marginVertical: 8 },
  error: { color: "#dc2626", marginBottom: 4 },
  inputRow: { flexDirection: "row", gap: 8, marginTop: 8, alignItems: "center" },
  input: { flex: 1, borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10 },
  send: { color: "#2563eb", fontWeight: "600", padding: 8 },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

- [ ] **Step 3: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add 'apps/mobile/app/(tabs)/chat.tsx' && git commit -m 'Phase 7: chat screen'"
```

---

### Task 8: Tasks screen

**Files:**
- Modify: `apps/mobile/app/(tabs)/tasks.tsx` (replace placeholder)

**Interfaces:**
- Consumes: `listTasks`, `updateTaskStatus`, `TaskOut`, `ApiError` from Task 2.

- [ ] **Step 1: Implement the tasks screen**

`apps/mobile/app/(tabs)/tasks.tsx`:

```tsx
import { useCallback, useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, StyleSheet, Switch, Text, TouchableOpacity, View } from "react-native";
import { ApiError, listTasks, updateTaskStatus, type TaskOut } from "../../src/lib/api";

type Filter = "open" | "done" | "all";

export default function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((f: Filter) => {
    listTasks(f === "all" ? undefined : f)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load tasks"));
  }, []);

  useEffect(() => {
    refresh(filter);
  }, [filter, refresh]);

  async function toggle(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.filterRow}>
        {(["open", "done", "all"] as Filter[]).map((f) => (
          <TouchableOpacity key={f} onPress={() => setFilter(f)}>
            <Text style={[styles.filterLabel, filter === f && styles.filterLabelActive]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={tasks}
        keyExtractor={(t) => t.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Switch value={item.status === "done"} onValueChange={() => toggle(item)} />
            <View style={styles.rowText}>
              <Text style={item.status === "done" ? styles.doneTitle : styles.title}>{item.title}</Text>
              {item.description && <Text style={styles.description}>{item.description}</Text>}
              {item.document_id && (
                <TouchableOpacity onPress={() => router.push(`/documents/${item.document_id}`)}>
                  <Text style={styles.link}>Source document</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No {filter !== "all" ? filter : ""} tasks.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  filterRow: { flexDirection: "row", gap: 16, marginBottom: 12 },
  filterLabel: { color: "#64748b", textTransform: "capitalize" },
  filterLabelActive: { color: "#0f172a", fontWeight: "600" },
  row: { flexDirection: "row", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  rowText: { flex: 1, gap: 2 },
  title: { fontSize: 15, fontWeight: "500" },
  doneTitle: { fontSize: 15, color: "#94a3b8", textDecorationLine: "line-through" },
  description: { fontSize: 13, color: "#64748b" },
  link: { fontSize: 12, color: "#2563eb" },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
  error: { color: "#dc2626", marginBottom: 8 },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

- [ ] **Step 3: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add 'apps/mobile/app/(tabs)/tasks.tsx' && git commit -m 'Phase 7: tasks screen'"
```

---

### Task 9: Entity list screen

**Files:**
- Modify: `apps/mobile/app/(tabs)/entities/index.tsx` (replace placeholder)

**Interfaces:**
- Consumes: `listEntities`, `EntityOut`, `ApiError` from Task 2.

- [ ] **Step 1: Implement the entity list screen**

`apps/mobile/app/(tabs)/entities/index.tsx`:

```tsx
import { useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { listEntities, type EntityOut } from "../../../src/lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
};

const TYPES = ["", "person", "organization", "location", "other"];

export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");

  useEffect(() => {
    listEntities(q || undefined, entityType || undefined).then(setEntities);
  }, [q, entityType]);

  return (
    <View style={styles.container}>
      <TextInput style={styles.search} placeholder="Search entities..." value={q} onChangeText={setQ} />
      <View style={styles.typeRow}>
        {TYPES.map((t) => (
          <TouchableOpacity key={t || "all"} onPress={() => setEntityType(t)}>
            <Text style={[styles.typeLabel, entityType === t && styles.typeLabelActive]}>{t || "all"}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <FlatList
        data={entities}
        keyExtractor={(e) => e.id}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => router.push(`/entities/${item.id}`)}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={[styles.badge, { color: TYPE_COLORS[item.entity_type] ?? TYPE_COLORS.other }]}>
              {item.entity_type}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No entities found.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  search: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 8 },
  typeRow: { flexDirection: "row", gap: 12, marginBottom: 12, flexWrap: "wrap" },
  typeLabel: { color: "#64748b", textTransform: "capitalize" },
  typeLabelActive: { color: "#0f172a", fontWeight: "600" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  name: { fontSize: 15, fontWeight: "500" },
  badge: { fontSize: 12 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

- [ ] **Step 3: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add 'apps/mobile/app/(tabs)/entities/' && git commit -m 'Phase 7: entity list screen'"
```

---

### Task 10: Entity graph screen

**Files:**
- Create: `apps/mobile/src/components/EntityGraph.tsx`
- Create: `apps/mobile/app/entities/[id].tsx`

**Interfaces:**
- Consumes: `getEntityGraph`, `EntityGraphOut`, `GraphNode`, `ApiError` from Task 2.
- Produces: `EntityGraph` component (`props: { graph: EntityGraphOut, onSelectNode: (id: string) => void }`), used only by this task's screen.

- [ ] **Step 1: Implement the graph component with the transparent hit-target fix built in from the start**

`apps/mobile/src/components/EntityGraph.tsx`:

```tsx
import Svg, { Circle, G, Line, Rect, Text as SvgText } from "react-native-svg";
import type { EntityGraphOut, GraphNode } from "../lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
};

const WIDTH = 350;
const HEIGHT = 400;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };
const RADIUS = 130;
const NODE_RADIUS = 8;

function nodeColor(entityType: string): string {
  return TYPE_COLORS[entityType] ?? TYPE_COLORS.other;
}

export function EntityGraph({ graph, onSelectNode }: { graph: EntityGraphOut; onSelectNode: (id: string) => void }) {
  const positions = new Map<string, { x: number; y: number }>();
  positions.set(graph.center.id, CENTER);
  graph.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1) - Math.PI / 2;
    positions.set(node.id, {
      x: CENTER.x + RADIUS * Math.cos(angle),
      y: CENTER.y + RADIUS * Math.sin(angle),
    });
  });

  return (
    <Svg width={WIDTH} height={HEIGHT}>
      {graph.edges.map((edge, i) => {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) return null;
        const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
        return (
          <G key={i}>
            <Line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#94a3b8" strokeWidth={1.5} />
            <SvgText x={mid.x} y={mid.y} fontSize={9} fill="#64748b" textAnchor="middle">
              {edge.relationship_type}
            </SvgText>
          </G>
        );
      })}

      {graph.nodes.map((node: GraphNode) => {
        const pos = positions.get(node.id)!;
        return (
          <G key={node.id} onPress={() => onSelectNode(node.id)}>
            {/* Transparent hit-target covering the circle + label together, built in
                from the start per ADR 0016 -- SVG hit-testing is per-painted-shape,
                not per-bounding-box, so the gap between the circle and its label
                below it would otherwise be an unclickable dead zone (found and fixed
                on the web version in Phase 5c; touch targets are coarser than a
                mouse, so the same problem is at least as likely here). */}
            <Rect x={pos.x - 45} y={pos.y - NODE_RADIUS - 2} width={90} height={NODE_RADIUS + 30} fill="transparent" />
            <Circle cx={pos.x} cy={pos.y} r={NODE_RADIUS} fill={nodeColor(node.entity_type)} />
            <SvgText x={pos.x} y={pos.y + NODE_RADIUS + 14} fontSize={10} fill="#1e293b" textAnchor="middle">
              {node.name.length > 20 ? `${node.name.slice(0, 20)}…` : node.name}
            </SvgText>
          </G>
        );
      })}

      <Circle cx={CENTER.x} cy={CENTER.y} r={NODE_RADIUS + 2} fill={nodeColor(graph.center.entity_type)} stroke="#0f172a" strokeWidth={2} />
      <SvgText x={CENTER.x} y={CENTER.y + NODE_RADIUS + 18} fontSize={11} fontWeight="600" fill="#0f172a" textAnchor="middle">
        {graph.center.name}
      </SvgText>
    </Svg>
  );
}
```

- [ ] **Step 2: Implement the screen wiring it in**

`apps/mobile/app/entities/[id].tsx`:

```tsx
import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { ApiError, getEntityGraph, type EntityGraphOut } from "../../src/lib/api";
import { EntityGraph } from "../../src/components/EntityGraph";

export default function EntityGraphScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [graph, setGraph] = useState<EntityGraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGraph(null);
    setError(null);
    getEntityGraph(id)
      .then(setGraph)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load graph"));
  }, [id]);

  if (error) return <View style={styles.container}><Text style={styles.error}>{error}</Text></View>;
  if (!graph) return <View style={styles.container}><ActivityIndicator /></View>;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{graph.center.name}</Text>
      <Text style={styles.meta}>
        {graph.center.entity_type} · {graph.nodes.length} direct relationship{graph.nodes.length === 1 ? "" : "s"}
      </Text>
      {graph.nodes.length === 0 ? (
        <Text style={styles.empty}>No known relationships for this entity yet.</Text>
      ) : (
        <EntityGraph graph={graph} onSelectNode={(nodeId) => router.push(`/entities/${nodeId}`)} />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  title: { fontSize: 20, fontWeight: "600" },
  meta: { fontSize: 13, color: "#64748b", marginBottom: 12 },
  empty: { color: "#64748b", marginTop: 20 },
  error: { color: "#dc2626" },
});
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx tsc --noEmit"
```

- [ ] **Step 4: Commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add apps/mobile/src/components/ apps/mobile/app/entities/ && git commit -m 'Phase 7: entity graph screen (react-native-svg radial layout)'"
```

---

### Task 11: Live verification, README update, final commit

**Files:**
- Modify: `README.md` (status line, phase list, new "Mobile app" paragraph)
- No code files (verification + docs only)

**Interfaces:**
- Consumes: the complete app from Tasks 1-10.

- [ ] **Step 1: Run the full test suite**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx vitest run && npx tsc --noEmit"
```

Expected: all `vitest` tests pass, `tsc` reports no errors.

- [ ] **Step 2: Start the Expo dev server and connect a real client**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains/apps/mobile && npx expo start --tunnel"
```

This needs a human with the Expo Go app on their phone to scan the printed QR code (Expo's `--tunnel` mode routes through Expo's relay so a phone on a different network than this server can still reach the dev server — necessary here since the phone won't be on the same LAN as this VM). **This step cannot be completed by the agent alone** — hand off to the user for the actual device connection, then resume verification once connected.

- [ ] **Step 3: Walk through every screen against the live backend**

With a real device connected: log in with a real account, verify the document list loads and pull-to-refresh works, open a document detail, run a search, send a chat message and verify citations navigate correctly, toggle a task, browse entities, open an entity graph and tap a neighbor to re-center. This is the same live-testing discipline used for every phase of `apps/web` — confirm each screen against real data, not just "it compiles."

- [ ] **Step 4: Update README.md**

Add "Phase 7 (mobile app)" to the phase list and a short paragraph describing what shipped, following the exact pattern of every prior phase's README update in this project (see the existing Phase 5a-6d entries for the established voice/format).

- [ ] **Step 5: Final commit**

```bash
ssh root@195.90.216.230 "cd /opt/collabrains && git add README.md && git commit -m 'Phase 7: mobile app verified end-to-end, update README' && git push origin main"
```
