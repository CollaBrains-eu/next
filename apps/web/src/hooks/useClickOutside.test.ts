import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { useClickOutside } from "./useClickOutside";

describe("useClickOutside", () => {
  it("calls onOutside when a click lands outside the ref'd element", () => {
    const onOutside = vi.fn();
    const inside = document.createElement("div");
    document.body.appendChild(inside);
    const ref = { current: inside };

    renderHook(() => useClickOutside(ref, true, onOutside));
    fireEvent.mouseDown(document.body);

    expect(onOutside).toHaveBeenCalledOnce();
    document.body.removeChild(inside);
  });

  it("does not call onOutside when the click lands inside the ref'd element", () => {
    const onOutside = vi.fn();
    const inside = document.createElement("div");
    document.body.appendChild(inside);
    const ref = { current: inside };

    renderHook(() => useClickOutside(ref, true, onOutside));
    fireEvent.mouseDown(inside);

    expect(onOutside).not.toHaveBeenCalled();
    document.body.removeChild(inside);
  });

  it("does nothing when inactive", () => {
    const onOutside = vi.fn();
    const ref = { current: null };
    renderHook(() => useClickOutside(ref, false, onOutside));
    fireEvent.mouseDown(document.body);
    expect(onOutside).not.toHaveBeenCalled();
  });
});
