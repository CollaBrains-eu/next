import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BulkActionBar } from "./BulkActionBar";

describe("BulkActionBar", () => {
  it("renders nothing when count is 0", () => {
    const { container } = render(<BulkActionBar count={0} onCancel={() => {}} actions={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the count when greater than 0", () => {
    render(<BulkActionBar count={3} onCancel={() => {}} actions={[]} />);
    expect(screen.getByText((_, element) => element?.textContent === "3 selected")).toBeInTheDocument();
  });

  it("renders every action as a clickable button", () => {
    const onExport = vi.fn();
    const onDelete = vi.fn();
    render(
      <BulkActionBar
        count={2}
        onCancel={() => {}}
        actions={[
          { label: "Export", onClick: onExport },
          { label: "Delete", onClick: onDelete, variant: "danger" },
        ]}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(onExport).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("applies danger styling to actions marked variant danger", () => {
    render(
      <BulkActionBar
        count={1}
        onCancel={() => {}}
        actions={[{ label: "Delete", onClick: () => {}, variant: "danger" }]}
      />
    );
    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass("bg-danger");
  });

  it("calls onCancel when Cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<BulkActionBar count={2} onCancel={onCancel} actions={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
