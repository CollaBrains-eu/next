import { expect } from "@playwright/test";
import { test } from "./fixtures";

test("document listing renders for an authenticated user", async ({ authedPage: page }) => {
  await page.goto("/documents");
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.getByRole("heading", { name: /documents/i })).toBeVisible();
  // A fresh disposable test user has no documents -- the empty state is the
  // correct, expected render here, not a list. Either a populated list or
  // the empty state is a legitimate pass; a crash/blank page is not.
  const hasEmptyState = await page.getByText(/no documents/i).isVisible().catch(() => false);
  const hasTable = await page.getByRole("table").isVisible().catch(() => false);
  expect(hasEmptyState || hasTable, "expected either the empty state or a document list").toBeTruthy();
});
