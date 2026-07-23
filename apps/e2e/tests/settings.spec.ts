import { expect } from "@playwright/test";
import { test } from "./fixtures";

test("authenticated user can reach settings/profile", async ({ authedPage: page }) => {
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: /settings/i })).toBeVisible();
});
