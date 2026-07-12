import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "./src/lib/i18n";

// jsdom has no IntersectionObserver -- framer-motion's whileInView (used by Landing)
// needs one to mount at all, so stub it out rather than let every scroll animation fail.
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error -- test-only stub, not a spec-complete IntersectionObserver
globalThis.IntersectionObserver = MockIntersectionObserver;

afterEach(() => {
  cleanup();
});
