// Carries a plan choice made on the anonymous Landing page's pricing cards
// through registration + email verification (Priority 3 commercial SaaS,
// ADR 0074) -- the verification link is opened by clicking an emailed link,
// which may land in a different tab than the one that started registration,
// so in-memory/component state can't survive the round-trip. localStorage
// does, for the common same-device/same-browser case; a different device
// just means the user picks a plan manually in Settings afterward, same as
// today.
const KEY = "collabrains_pending_plan";

export function setPendingPlan(plan: string): void {
  window.localStorage.setItem(KEY, plan);
}

export function consumePendingPlan(): string | null {
  const plan = window.localStorage.getItem(KEY);
  if (plan) window.localStorage.removeItem(KEY);
  return plan;
}
