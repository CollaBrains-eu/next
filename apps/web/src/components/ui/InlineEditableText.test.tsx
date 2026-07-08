import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InlineEditableText } from "./InlineEditableText";

describe("InlineEditableText", () => {
  it("renders the value as plain text with an edit button", () => {
    render(<InlineEditableText value="factuur.pdf" onSave={() => {}} />);
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit")).toBeInTheDocument();
  });

  it("clicking Edit shows an input pre-filled with the current value", () => {
    render(<InlineEditableText value="factuur.pdf" onSave={() => {}} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    expect(screen.getByRole("textbox")).toHaveValue("factuur.pdf");
  });

  it("Enter commits the new value and calls onSave, reverting to text display", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).toHaveBeenCalledWith("renamed.pdf");
    expect(screen.getByText("renamed.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("blur also commits the new value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.blur(input);
    expect(onSave).toHaveBeenCalledWith("renamed.pdf");
  });

  it("Escape cancels without calling onSave and reverts to the original value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
  });

  it("does not call onSave with an empty/whitespace-only value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
  });
});
