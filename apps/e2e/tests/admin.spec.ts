import { expect } from "@playwright/test";
import { test } from "./fixtures";

test("admin user can reach the admin dashboard", async ({ adminPage: page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("non-admin user is redirected away from /admin", async ({ authedPage: page }) => {
  await page.goto("/admin");
  // AdminRoute (src/components/AdminRoute.tsx) redirects non-admins to "/"
  // rather than showing a 403 page.
  await expect(page).toHaveURL(/\/$/);
});
