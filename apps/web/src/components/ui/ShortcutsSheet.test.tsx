import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ShortcutsSheet } from "./ShortcutsSheet";

describe("ShortcutsSheet", () => {
  it("renders nothing when closed", () => {
    render(<ShortcutsSheet open={false} onClose={() => {}} />);
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("lists the known shortcuts when open", () => {
    render(<ShortcutsSheet open onClose={() => {}} />);
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Open command palette")).toBeInTheDocument();
    expect(screen.getByText("⌘K")).toBeInTheDocument();
    expect(screen.getByText("Show this sheet")).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(<ShortcutsSheet open onClose={onClose} />);
    fireEvent.click(screen.getByTestId("shortcuts-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<ShortcutsSheet open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
