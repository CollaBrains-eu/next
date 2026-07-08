import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommandPalette } from "./CommandPalette";

const items = [
  { label: "Go to Documents", onSelect: vi.fn() },
  { label: "Go to Cases", onSelect: vi.fn() },
  { label: "Go to Vehicles", onSelect: vi.fn() },
];

beforeEach(() => {
  items.forEach((item) => item.onSelect.mockClear());
});

describe("CommandPalette", () => {
  it("renders nothing when closed", () => {
    render(<CommandPalette open={false} onClose={() => {}} items={items} />);
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
  });

  it("renders all items when open with an empty query", () => {
    render(<CommandPalette open onClose={() => {}} items={items} />);
    expect(screen.getByText("Go to Documents")).toBeInTheDocument();
    expect(screen.getByText("Go to Cases")).toBeInTheDocument();
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
  });

  it("filters items as you type", () => {
    render(<CommandPalette open onClose={() => {}} items={items} />);
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "vehicles" } });
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
    expect(screen.queryByText("Go to Documents")).not.toBeInTheDocument();
  });

  it("calls the matching item's onSelect and onClose when clicked", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    fireEvent.click(screen.getByText("Go to Cases"));
    expect(items[1].onSelect).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("ArrowDown moves the selection and Enter selects it", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(items[1].onSelect).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
