import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("expo-secure-store", () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: vi.fn(async (key: string) => store.get(key) ?? null),
    setItemAsync: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    deleteItemAsync: vi.fn(async (key: string) => {
      store.delete(key);
    }),
  };
});

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

  it("sends the login body as a plain encoded string, not a URLSearchParams instance", async () => {
    // Regression test: React Native's fetch does not reliably serialize a
    // URLSearchParams body the way browser fetch does -- on a real device
    // this silently sent an empty body, and the backend rejected it with
    // "username: Field required, password: Field required" even though the
    // Content-Type header and fields all looked correct in code review.
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ access_token: "tok", token_type: "bearer" }), { status: 200 }),
    );

    await login("admin1", "hunter2");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(typeof init.body).toBe("string");
    expect(init.body).toBe("username=admin1&password=hunter2");
  });
});
