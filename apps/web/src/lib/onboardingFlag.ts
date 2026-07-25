// Marks that a freshly self-registered account should see the guided
// onboarding wizard (Onboard.tsx's wizard mode) the next time it lands
// authenticated on "/" -- set at registration time (Register.tsx) since the
// actual login happens later, possibly in a different browser tab, when the
// emailed verification link is clicked (same cross-tab constraint as
// pendingPlan.ts, hence the same localStorage-backed approach).
const KEY = "collabrains_needs_onboarding";

export function markOnboardingPending(): void {
  window.localStorage.setItem(KEY, "1");
}

export function needsOnboarding(): boolean {
  return window.localStorage.getItem(KEY) === "1";
}

export function clearOnboardingPending(): void {
  window.localStorage.removeItem(KEY);
}
