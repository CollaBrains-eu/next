import { expect } from "@playwright/test";
import { test } from "./fixtures";

// Runs only under the "mobile" Playwright project (iPhone 13 profile, see
// playwright.config.ts). Scoped to pages already known to handle small
// viewports correctly; Workspace.tsx (/documents) and Vehicles.tsx are
// tracked separately (ADR 0066 Priority 2 item 5) since the P1 audit found
// they have zero responsive breakpoint classes today -- adding an
// assertion here ahead of that fix would just commit a known-red test.

async function hasNoHorizontalOverflow(page: import("@playwright/test").Page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
}

test("landing page has no horizontal overflow on a phone viewport", async ({ page }) => {
  await page.goto("/");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
  await expect(page.getByRole("button", { name: /log in/i })).toBeVisible();
});

test("login form has no horizontal overflow and controls stay reachable", async ({ page }) => {
  await page.goto("/login");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
  await expect(page.getByLabel(/username/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
});

test("dashboard has no horizontal overflow on a phone viewport", async ({ authedPage: page }) => {
  await page.goto("/");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
});
