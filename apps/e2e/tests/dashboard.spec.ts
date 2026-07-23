import { expect } from "@playwright/test";
import { test } from "./fixtures";

test("authenticated user's dashboard loads", async ({ authedPage: page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/$/);
  // RootRoute renders Dashboard (not Landing) once `user` is set -- a
  // level-1 heading with real content, not the landing page's marketing copy.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: /log in/i })).not.toBeVisible();
});
