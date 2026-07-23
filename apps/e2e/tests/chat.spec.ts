import { expect } from "@playwright/test";
import { test } from "./fixtures";

// Deliberately availability-only, not a real generation round trip: this
// project's chat model is CPU-bound and can take well over a minute per
// reply on its production host (see docs/deployment/ai-optimization.md), and
// there's no Ollama in the CI job this suite runs in (see ADR 0069) -- a
// real inference call here would be slow, flaky, and test infrastructure
// this suite doesn't have, not the app. This checks the feature is present
// and reachable, which is what "AI chat availability" means for a smoke
// suite; a real generation test belongs in a slower, separately-scheduled
// suite if one gets built later.
test("AI chat page is reachable and the input is available", async ({ authedPage: page }) => {
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/chat$/);
  // ChatInput is a plain textarea with no visible submit button -- Enter
  // submits the enclosing form via form.requestSubmit(). Its presence and
  // enabled state is what "available" means here.
  const input = page.getByPlaceholder(/ask a question/i);
  await expect(input).toBeVisible();
  await expect(input).toBeEnabled();
});
