import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DeleteConfirmButton } from "./DeleteConfirmButton";

function renderButton(onConfirm = vi.fn()) {
  render(
    <DeleteConfirmButton
      confirmTitle='Delete "Test item"?'
      confirmBody="This cannot be undone."
      confirmLabel="Delete item"
      onConfirm={onConfirm}
      deleting={false}
    />
  );
  return onConfirm;
}

describe("DeleteConfirmButton", () => {
  it("does not show the confirmation modal until the trigger is clicked", () => {
    renderButton();
    expect(screen.queryByText(/cannot be undone/i)).not.toBeInTheDocument();
  });

  it("opens a confirmation modal with distinct labels for trigger vs. confirm", () => {
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByText('Delete "Test item"?')).toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete item" })).toBeInTheDocument();
  });

  it("confirming calls onConfirm and closes the modal", () => {
    const onConfirm = renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete item" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/cannot be undone/i)).not.toBeInTheDocument();
  });

  it("cancelling does not call onConfirm", () => {
    const onConfirm = renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByText(/cannot be undone/i)).not.toBeInTheDocument();
  });
});
