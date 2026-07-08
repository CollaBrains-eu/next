import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "./toast";

function ToastTrigger({ onUndo }: { onUndo?: () => void }) {
  const { showToast } = useToast();
  return <button onClick={() => showToast("Case deleted", onUndo ? { onUndo } : undefined)}>Trigger</button>;
}

describe("toast system", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows a toast with the given text", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    expect(screen.getByText("Case deleted")).toBeInTheDocument();
  });

  it("auto-dismisses after 4000ms", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    expect(screen.getByText("Case deleted")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Case deleted")).not.toBeInTheDocument();
  });

  it("renders an Undo button and calls onUndo when clicked", () => {
    const onUndo = vi.fn();
    render(
      <ToastProvider>
        <ToastTrigger onUndo={onUndo} />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    fireEvent.click(screen.getByText("Undo"));
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it("throws a clear error if useToast is called outside a ToastProvider", () => {
    function Orphan() {
      useToast();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow("useToast must be used within a ToastProvider");
  });
});
