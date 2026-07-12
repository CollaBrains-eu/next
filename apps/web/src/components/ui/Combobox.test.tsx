import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Combobox } from "./Combobox";

const OPTIONS = [
  { id: "1", label: "Jane Doe" },
  { id: "2", label: "John Roe" },
];

describe("Combobox", () => {
  it("renders selected items as removable chips", () => {
    render(<Combobox options={OPTIONS} selected={[OPTIONS[0]]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Remove Jane Doe" })).toBeInTheDocument();
  });

  it("adds an option to the selection when clicked", () => {
    const onChange = vi.fn();
    render(<Combobox options={OPTIONS} selected={[]} onChange={onChange} />);
    fireEvent.click(screen.getByPlaceholderText("Search…"));
    fireEvent.click(screen.getByRole("button", { name: "Jane Doe" }));
    expect(onChange).toHaveBeenCalledWith([OPTIONS[0]]);
  });

  it("removes an option from the selection when its chip's remove button is clicked", () => {
    const onChange = vi.fn();
    render(<Combobox options={OPTIONS} selected={[OPTIONS[0]]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove Jane Doe" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("filters options by the typed query", () => {
    render(<Combobox options={OPTIONS} selected={[]} onChange={() => {}} />);
    fireEvent.click(screen.getByPlaceholderText("Search…"));
    fireEvent.change(screen.getByPlaceholderText("Search…"), { target: { value: "John" } });
    expect(screen.queryByRole("button", { name: "Jane Doe" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "John Roe" })).toBeInTheDocument();
  });

  it("replaces rather than appends the selection in single-select mode", () => {
    const onChange = vi.fn();
    render(<Combobox multiple={false} options={OPTIONS} selected={[OPTIONS[0]]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("textbox"));
    fireEvent.click(screen.getByRole("button", { name: "John Roe" }));
    expect(onChange).toHaveBeenCalledWith([OPTIONS[1]]);
  });

  it("closes the dropdown after picking an option in single-select mode", () => {
    render(<Combobox multiple={false} options={OPTIONS} selected={[]} onChange={() => {}} />);
    fireEvent.click(screen.getByPlaceholderText("Search…"));
    fireEvent.click(screen.getByRole("button", { name: "Jane Doe" }));
    expect(screen.getByRole("listbox")).not.toHaveClass("pointer-events-auto");
  });
});
