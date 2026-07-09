import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Dropdown } from "./Dropdown";

describe("Dropdown", () => {
  it("hides the menu until the trigger is clicked", () => {
    render(<Dropdown trigger="Options" options={[{ label: "Edit", onSelect: () => {} }]} />);
    expect(screen.getByRole("menu")).toHaveClass("pointer-events-none");
    fireEvent.click(screen.getByRole("button", { name: "Options" }));
    expect(screen.getByRole("menu")).toHaveClass("pointer-events-auto");
  });

  it("calls onSelect and closes when an option is clicked", () => {
    const onSelect = vi.fn();
    render(<Dropdown trigger="Options" options={[{ label: "Edit", onSelect }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Options" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Edit" }));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(screen.getByRole("menu")).toHaveClass("pointer-events-none");
  });

  it("closes on Escape", () => {
    render(<Dropdown trigger="Options" options={[{ label: "Edit", onSelect: () => {} }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Options" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("menu")).toHaveClass("pointer-events-none");
  });
});
