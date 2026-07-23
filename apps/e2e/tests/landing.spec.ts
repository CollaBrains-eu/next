import { test, expect } from "@playwright/test";

test.describe("landing page", () => {
  test("anonymous visitor sees the landing page, not a login redirect", async ({ page }) => {
    await page.goto("/");
    // RootRoute renders <Landing/> directly for a logged-out visitor rather
    // than redirecting -- so the URL should stay "/", not bounce to /login.
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("button", { name: /log in/i })).toBeVisible();
  });

  test("has no uncaught console errors on first load", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors, `console errors: ${errors.join(", ")}`).toEqual([]);
  });
});
