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
