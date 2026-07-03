import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, clearToken, login, request, setToken } from "./api";

describe("api request()", () => {
  beforeEach(() => {
    clearToken();
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
    // Regression test: login() sends form-urlencoded, but the generic wrapper
    // used to unconditionally overwrite Content-Type with application/json,
    // which made the OAuth2 token endpoint reject the request with a 422.
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ access_token: "tok", token_type: "bearer" }), { status: 200 }),
    );

    await login("admin1", "hunter2");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).get("Content-Type")).toBe("application/x-www-form-urlencoded");
  });

  it("does not set Content-Type for FormData bodies (browser sets the multipart boundary)", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("{}", { status: 200 }));

    await request("/documents", { method: "POST", body: new FormData() });

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).has("Content-Type")).toBe(false);
  });

  it("attaches a bearer token when one is stored", async () => {
    setToken("secret-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("{}", { status: 200 }));

    await request("/auth/me");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer secret-token");
  });

  it("throws ApiError with the parsed detail message on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ detail: "not linked" }), { status: 403, statusText: "Forbidden" }),
    );

    await expect(request("/chat")).rejects.toMatchObject(
      new ApiError(403, "not linked"),
    );
  });
});
