// Plausible (Priority 3 commercial SaaS, ADR 0074) -- cookieless, no
// personal data collected, GDPR-compliant without a consent banner, same
// privacy stance as Sentry's dataCollection settings in instrument.ts.
// Stays fully inert (script never injected, window.plausible never called)
// until VITE_PLAUSIBLE_DOMAIN is configured -- same "no key means no calls"
// contract instrument.ts/email_client.py/sentry_config.py all use.
const domain = import.meta.env.VITE_PLAUSIBLE_DOMAIN;
// Defaults to Plausible's hosted script; pass a self-hosted instance's own
// script URL here instead if this ever moves off Plausible Cloud.
const scriptSrc = import.meta.env.VITE_PLAUSIBLE_SCRIPT_SRC || "https://plausible.io/js/script.js";

declare global {
  interface Window {
    plausible?: ((...args: unknown[]) => void) & { q?: unknown[] };
  }
}

export function isAnalyticsConfigured(): boolean {
  return Boolean(domain);
}

export function initAnalytics(): void {
  if (!domain) return;
  // Queueing shim from Plausible's own docs -- lets trackPageview() calls
  // made before the external script finishes loading queue up instead of
  // being silently dropped.
  window.plausible =
    window.plausible ||
    ((...args: unknown[]) => {
      (window.plausible!.q = window.plausible!.q || []).push(args);
    });

  const script = document.createElement("script");
  script.defer = true;
  script.dataset.domain = domain;
  script.src = scriptSrc;
  document.head.appendChild(script);
}

export function trackPageview(): void {
  if (!domain) return;
  window.plausible?.("pageview");
}
