import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { useEscapeToClose } from "./useEscapeToClose";

describe("useEscapeToClose", () => {
  it("calls onClose when Escape is pressed and active is true", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(true, onClose));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when active is false", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(false, onClose));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not call onClose for other keys", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(true, onClose));
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("removes its listener when active becomes false", () => {
    const onClose = vi.fn();
    const { rerender } = renderHook(({ active }) => useEscapeToClose(active, onClose), {
      initialProps: { active: true },
    });
    rerender({ active: false });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
