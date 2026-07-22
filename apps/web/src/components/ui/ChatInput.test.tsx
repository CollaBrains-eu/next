import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "./ChatInput";

function renderInForm(onSubmit: () => void, disabled = false) {
  return render(
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <ChatInput value="" onChange={() => {}} placeholder="Type…" disabled={disabled} />
    </form>
  );
}

describe("ChatInput", () => {
  it("renders the placeholder and current value", () => {
    render(
      <form>
        <ChatInput value="hello" onChange={() => {}} placeholder="Type…" />
      </form>
    );
    expect(screen.getByPlaceholderText("Type…")).toHaveValue("hello");
  });

  it("calls onChange with the new value when typed into", () => {
    const onChange = vi.fn();
    render(
      <form>
        <ChatInput value="" onChange={onChange} placeholder="Type…" />
      </form>
    );
    fireEvent.change(screen.getByPlaceholderText("Type…"), { target: { value: "hi" } });
    expect(onChange).toHaveBeenCalledWith("hi");
  });

  it("submits the enclosing form on Enter without Shift", () => {
    const onSubmit = vi.fn();
    renderInForm(onSubmit);
    fireEvent.keyDown(screen.getByPlaceholderText("Type…"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not submit the form on Shift+Enter", () => {
    const onSubmit = vi.fn();
    renderInForm(onSubmit);
    fireEvent.keyDown(screen.getByPlaceholderText("Type…"), { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables the textarea when disabled is true", () => {
    render(
      <form>
        <ChatInput value="" onChange={() => {}} placeholder="Type…" disabled />
      </form>
    );
    expect(screen.getByPlaceholderText("Type…")).toBeDisabled();
  });
});
