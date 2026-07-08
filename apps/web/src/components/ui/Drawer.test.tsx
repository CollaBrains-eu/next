import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Drawer } from "./Drawer";

const tabs = [
  { id: "details", label: "Details", content: <p>Detail content</p> },
  { id: "activity", label: "Activity", content: <p>Activity content</p> },
];

describe("Drawer", () => {
  it("renders nothing when closed", () => {
    render(<Drawer open={false} onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    expect(screen.queryByText("factuur.pdf")).not.toBeInTheDocument();
  });

  it("renders the title and the first tab's content by default when open", () => {
    render(<Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
    expect(screen.getByText("Detail content")).toBeInTheDocument();
    expect(screen.queryByText("Activity content")).not.toBeInTheDocument();
  });

  it("switches tab content when a tab is clicked", () => {
    render(<Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    fireEvent.click(screen.getByText("Activity"));
    expect(screen.getByText("Activity content")).toBeInTheDocument();
    expect(screen.queryByText("Detail content")).not.toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="factuur.pdf" tabs={tabs} />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="factuur.pdf" tabs={tabs} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders the footer when given", () => {
    render(
      <Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} footer={<button>Download</button>}>
      </Drawer>
    );
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});
