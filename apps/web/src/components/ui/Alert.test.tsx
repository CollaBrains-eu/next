import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Alert } from "./Alert";

describe("Alert", () => {
  it("renders title and children", () => {
    render(
      <Alert variant="warning" title="Heads up">
        Something needs attention.
      </Alert>,
    );
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    expect(screen.getByText("Something needs attention.")).toBeInTheDocument();
  });

  it("does not render a dismiss button unless dismissible", () => {
    render(<Alert variant="info">Info only</Alert>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("calls onDismiss and hides itself when dismissed", () => {
    const onDismiss = vi.fn();
    render(
      <Alert variant="danger" dismissible onDismiss={onDismiss}>
        Something failed.
      </Alert>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(screen.queryByText("Something failed.")).not.toBeInTheDocument();
  });
});
