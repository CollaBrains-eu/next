import { defineConfig, devices } from "@playwright/test";

// Smoke suite only -- see docs/adr/0069-playwright-smoke-suite.md for scope
// and why. Assumes the app (frontend + api + postgres + redis + openldap)
// is already running and reachable at BASE_URL; this config does not start
// anything itself, since orchestrating that differs between CI (docker
// compose, see .github/workflows/ci.yml) and a local dev stack a developer
// may already have up.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:4173";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /responsive\.spec\.ts/,
    },
    {
      name: "mobile",
      // Responsive-layout checks (ADR 0066 P2 item 2) run against a real
      // device profile rather than a bare viewport resize, so touch/UA
      // behavior matches what a real phone visitor gets. Chromium-based
      // (Pixel 7), not an iOS/WebKit profile: this suite is checking
      // responsive breakpoints, not engine-specific rendering, and WebKit
      // isn't installable on every dev machine (e.g. Playwright's bundled
      // WebKit build doesn't support macOS 13) -- Chromium keeps this
      // suite runnable everywhere without losing what it's actually for.
      use: { ...devices["Pixel 7"] },
      testMatch: /responsive\.spec\.ts/,
    },
  ],
});
