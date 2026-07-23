import { test, expect } from "@playwright/test";
import { TEST_USER, loginViaUi } from "./fixtures";

test.describe("login / authentication flow", () => {
  test("real credentials via the actual form land on the dashboard", async ({ page }) => {
    test.skip(!TEST_USER.username, "E2E_TEST_USERNAME/PASSWORD not set");
    await loginViaUi(page, TEST_USER.username, TEST_USER.password);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const token = await page.evaluate(() => window.localStorage.getItem("collabrains_token"));
    expect(token).toBeTruthy();
  });

  test("wrong password shows an error and does not navigate away from /login", async ({ page }) => {
    test.skip(!TEST_USER.username, "E2E_TEST_USERNAME/PASSWORD not set");
    await loginViaUi(page, TEST_USER.username, "definitely-the-wrong-password");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText(/incorrect|invalid|failed/i)).toBeVisible();
  });

  test("visiting a protected route while logged out redirects to /login", async ({ page }) => {
    await page.goto("/documents");
    await expect(page).toHaveURL(/\/login$/);
  });
});
