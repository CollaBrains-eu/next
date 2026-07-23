import { test as base, expect, type Page } from "@playwright/test";

// Credentials for disposable test users, provisioned by whatever runs this
// suite (CI: .github/workflows/ci.yml creates them via ldap_auth.create_user,
// the same mechanism used for every prior live-verification pass in this
// project -- see ADR 0065/0067). Never real user accounts.
export const TEST_USER = {
  username: process.env.E2E_TEST_USERNAME ?? "",
  password: process.env.E2E_TEST_PASSWORD ?? "",
};
export const ADMIN_USER = {
  username: process.env.E2E_ADMIN_USERNAME ?? "",
  password: process.env.E2E_ADMIN_PASSWORD ?? "",
};

function requireCreds(creds: { username: string; password: string }, label: string) {
  if (!creds.username || !creds.password) {
    throw new Error(
      `${label} credentials are not set -- export E2E_TEST_USERNAME/E2E_TEST_PASSWORD ` +
        `(and E2E_ADMIN_USERNAME/E2E_ADMIN_PASSWORD for admin tests) before running this suite.`
    );
  }
}

/** Real UI login: types into the actual form and submits it. Used by the one
 * test that's supposed to exercise the login flow itself -- everything else
 * uses `loginViaApi` below, which is faster and doesn't re-test the same UI
 * path over and over. */
export async function loginViaUi(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/username/i).fill(username);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
}

/** Fast path: gets a real JWT from the real /auth/token endpoint (no mocking)
 * and seeds localStorage directly, skipping the UI form for tests that exist
 * to check what's *behind* login, not the login form itself. */
export async function loginViaApi(page: Page, username: string, password: string) {
  requireCreds({ username, password }, "Test user");
  const response = await page.request.post("/auth/token", {
    form: { username, password },
  });
  expect(response.ok(), `login failed for ${username}: ${response.status()}`).toBeTruthy();
  const { access_token: token } = await response.json();
  await page.addInitScript((t) => {
    window.localStorage.setItem("collabrains_token", t);
  }, token);
}

export const test = base.extend<{ authedPage: Page; adminPage: Page }>({
  authedPage: async ({ page }, use) => {
    requireCreds(TEST_USER, "Test user");
    await loginViaApi(page, TEST_USER.username, TEST_USER.password);
    await use(page);
  },
  adminPage: async ({ page }, use) => {
    requireCreds(ADMIN_USER, "Admin user");
    await loginViaApi(page, ADMIN_USER.username, ADMIN_USER.password);
    await use(page);
  },
});

export { expect };
