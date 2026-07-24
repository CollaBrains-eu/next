import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_ENV = { ...import.meta.env };

async function loadAnalytics() {
  vi.resetModules();
  return import("./analytics");
}

describe("analytics", () => {
  beforeEach(() => {
    document.head.innerHTML = "";
    delete window.plausible;
  });

  afterEach(() => {
    Object.assign(import.meta.env, ORIGINAL_ENV);
  });

  it("stays fully inert when no domain is configured", async () => {
    import.meta.env.VITE_PLAUSIBLE_DOMAIN = "";
    const { initAnalytics, trackPageview, isAnalyticsConfigured } = await loadAnalytics();

    expect(isAnalyticsConfigured()).toBe(false);
    initAnalytics();
    trackPageview();

    expect(document.head.querySelector("script")).toBeNull();
    expect(window.plausible).toBeUndefined();
  });

  it("injects the Plausible script and tracks pageviews when a domain is configured", async () => {
    import.meta.env.VITE_PLAUSIBLE_DOMAIN = "collabrains.eu";
    const { initAnalytics, trackPageview, isAnalyticsConfigured } = await loadAnalytics();

    expect(isAnalyticsConfigured()).toBe(true);
    initAnalytics();

    const script = document.head.querySelector("script");
    expect(script).not.toBeNull();
    expect(script?.dataset.domain).toBe("collabrains.eu");
    expect(script?.src).toBe("https://plausible.io/js/script.js");

    const plausibleSpy = vi.fn();
    window.plausible = plausibleSpy;
    trackPageview();
    expect(plausibleSpy).toHaveBeenCalledWith("pageview");
  });

  it("uses a self-hosted script URL when configured", async () => {
    import.meta.env.VITE_PLAUSIBLE_DOMAIN = "collabrains.eu";
    import.meta.env.VITE_PLAUSIBLE_SCRIPT_SRC = "https://plausible.example.com/js/script.js";
    const { initAnalytics } = await loadAnalytics();

    initAnalytics();
    expect(document.head.querySelector("script")?.src).toBe("https://plausible.example.com/js/script.js");
  });
});
