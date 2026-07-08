import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterChips } from "./FilterChips";

describe("FilterChips", () => {
  it("renders each chip's label with a remove button", () => {
    render(
      <FilterChips
        chips={[{ id: "status-ready", label: "Status: Ready" }]}
        onRemove={() => {}}
        addOptions={[]}
        onAdd={() => {}}
      />
    );
    expect(screen.getByText("Status: Ready")).toBeInTheDocument();
  });

  it("calls onRemove with the chip's id when its remove button is clicked", () => {
    const onRemove = vi.fn();
    render(
      <FilterChips
        chips={[{ id: "status-ready", label: "Status: Ready" }]}
        onRemove={onRemove}
        addOptions={[]}
        onAdd={() => {}}
      />
    );
    fireEvent.click(screen.getByLabelText("Remove Status: Ready"));
    expect(onRemove).toHaveBeenCalledWith("status-ready");
  });

  it("opens the add-filter menu and lists addOptions when the add button is clicked", () => {
    render(
      <FilterChips
        chips={[]}
        onRemove={() => {}}
        addOptions={[{ id: "type-pdf", label: "Type: PDF" }]}
        onAdd={() => {}}
      />
    );
    expect(screen.queryByText("Type: PDF")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("+ Add filter"));
    expect(screen.getByText("Type: PDF")).toBeInTheDocument();
  });

  it("calls onAdd with the chosen option and closes the menu", () => {
    const onAdd = vi.fn();
    render(
      <FilterChips
        chips={[]}
        onRemove={() => {}}
        addOptions={[{ id: "type-pdf", label: "Type: PDF" }]}
        onAdd={onAdd}
      />
    );
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Type: PDF"));
    expect(onAdd).toHaveBeenCalledWith({ id: "type-pdf", label: "Type: PDF" });
    expect(screen.queryByText("Type: PDF")).not.toBeInTheDocument();
  });
});
