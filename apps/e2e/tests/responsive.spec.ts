import { expect } from "@playwright/test";
import { test } from "./fixtures";

// Runs only under the "mobile" Playwright project (Pixel 7 profile, see
// playwright.config.ts). Workspace.tsx (/documents) was fixed for
// responsive overflow in Priority 2 item 5 (ADR 0066/0071) -- covered
// below now. Vehicles.tsx, also flagged by the original audit, turned out
// on inspection to already use flex-wrap throughout (a valid
// non-breakpoint-prefixed technique the audit's "count sm:/md:/lg:
// classes" method couldn't see), so it needs no fix and no dedicated test
// here beyond what the other pages already cover.

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

test("documents page (Workspace.tsx) has no horizontal overflow on a phone viewport", async ({ authedPage: page }) => {
  await page.goto("/documents");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
  await expect(page.getByRole("heading", { name: /documents/i })).toBeVisible();
});

// Found via manual QA at 320px (not this project's Pixel 7 width, but the
// same unwrapped-flex-row cause reproduces at any width narrow enough):
// the Organization card's "Invite a teammate" input+button row had no
// min-w-0 on the input, so the button got pushed past the viewport edge
// instead of the input shrinking first. Fixed in Settings.tsx.
test("settings page (Organization section) has no horizontal overflow on a phone viewport", async ({ authedPage: page }) => {
  await page.goto("/settings");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
});

// Same manual-QA pass: AdminDashboard's per-group tab row (the FEEDBACK/
// MONITORING/etc. groups) didn't wrap its own tabs, only whole groups
// wrapped against their siblings -- a long group like "Bug reports /
// Feedback / Support Tickets" could overflow on its own. Fixed by adding
// flex-wrap to that inner row too.
test("admin dashboard tab bar has no horizontal overflow on a phone viewport", async ({ adminPage: page }) => {
  await page.goto("/admin");
  expect(await hasNoHorizontalOverflow(page)).toBeTruthy();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});
