import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { useFocusTrap } from "./useFocusTrap";

function setUpContainer(): HTMLElement {
  const container = document.createElement("div");
  container.innerHTML = `
    <button id="first">First</button>
    <button id="middle">Middle</button>
    <button id="last">Last</button>
  `;
  document.body.appendChild(container);
  return container;
}

function useTestHarness(active: boolean, container: HTMLElement | null) {
  const ref = useRef<HTMLElement | null>(container);
  useFocusTrap(active, ref);
}

describe("useFocusTrap", () => {
  it("moves focus to the first focusable element on activation", () => {
    const container = setUpContainer();
    renderHook(() => useTestHarness(true, container));
    expect(document.activeElement).toBe(container.querySelector("#first"));
    container.remove();
  });

  it("wraps Tab from the last element back to the first", () => {
    const container = setUpContainer();
    renderHook(() => useTestHarness(true, container));
    const last = container.querySelector<HTMLElement>("#last")!;
    last.focus();
    const event = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    document.dispatchEvent(event);
    expect(document.activeElement).toBe(container.querySelector("#first"));
    container.remove();
  });

  it("wraps Shift+Tab from the first element back to the last", () => {
    const container = setUpContainer();
    renderHook(() => useTestHarness(true, container));
    const first = container.querySelector<HTMLElement>("#first")!;
    first.focus();
    const event = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(event);
    expect(document.activeElement).toBe(container.querySelector("#last"));
    container.remove();
  });

  it("restores focus to the previously-focused element on deactivation", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const container = setUpContainer();
    const { rerender, unmount } = renderHook(({ active }) => useTestHarness(active, container), {
      initialProps: { active: true },
    });
    expect(document.activeElement).toBe(container.querySelector("#first"));

    rerender({ active: false });
    expect(document.activeElement).toBe(trigger);

    unmount();
    trigger.remove();
    container.remove();
  });

  it("does nothing when inactive", () => {
    const container = setUpContainer();
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();

    renderHook(() => useTestHarness(false, container));
    expect(document.activeElement).toBe(outside);
    container.remove();
    outside.remove();
  });
});
