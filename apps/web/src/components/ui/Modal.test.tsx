import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    expect(screen.queryByText("Delete case?")).not.toBeInTheDocument();
  });

  it("renders the title and children when open", () => {
    render(
      <Modal open onClose={() => {}} title="Delete case?">
        <p>This can't be undone.</p>
      </Modal>
    );
    expect(screen.getByText("Delete case?")).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when the panel itself is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.click(screen.getByText("Body"));
    expect(onClose).not.toHaveBeenCalled();
  });
});
