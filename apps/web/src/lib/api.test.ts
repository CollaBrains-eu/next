import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, approveEntity, clearToken, downloadAppointmentIcs, login, request, setToken } from "./api";

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

describe("approveEntity", () => {
  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts to /entities/:id/approve and returns the updated entity", async () => {
    const mockEntity = { id: "e1", name: "Test", entity_type: "person", status: "confirmed", created_at: "2026-01-01T00:00:00Z" };
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify(mockEntity), { status: 200 }),
    );

    const result = await approveEntity("e1");

    expect(result.status).toBe("confirmed");
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/entities/e1/approve");
    expect(init.method).toBe("POST");
  });
});

describe("downloadAppointmentIcs", () => {
  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
    URL.createObjectURL = vi.fn(() => "blob:mock-url");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches the ics endpoint with the auth header and triggers a download", async () => {
    setToken("secret-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("BEGIN:VCALENDAR", { status: 200 }));
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    await downloadAppointmentIcs("a1", "appointment.ics");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/appointments/a1/ics");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer secret-token");
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    clickSpy.mockRestore();
  });

  it("throws ApiError on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("", { status: 404, statusText: "Not Found" }));

    await expect(downloadAppointmentIcs("missing", "x.ics")).rejects.toBeInstanceOf(ApiError);
  });
});
