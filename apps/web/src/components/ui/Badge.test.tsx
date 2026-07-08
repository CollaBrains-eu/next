import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Ready</Badge>);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default").closest("span")).toHaveClass("bg-accent-soft", "text-accent");
  });

  it("applies danger variant classes", () => {
    render(<Badge variant="danger">Failed</Badge>);
    expect(screen.getByText("Failed").closest("span")).toHaveClass("bg-danger-soft", "text-danger");
  });

  it("renders a pulsing dot when pulsing is true", () => {
    render(<Badge pulsing>Processing</Badge>);
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders a checkmark svg instead of a dot when ready is true", () => {
    render(<Badge ready>Ready</Badge>);
    expect(document.querySelector("svg")).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).not.toBeInTheDocument();
  });
});
