import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetadataList } from "./MetadataList";

describe("MetadataList", () => {
  it("renders every label and its value", () => {
    render(
      <MetadataList
        items={[
          { label: "Type", value: "application/pdf" },
          { label: "Status", value: "ready" },
        ]}
      />,
    );
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("application/pdf")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("accepts a ReactNode as a value, not just strings", () => {
    render(<MetadataList items={[{ label: "Chunks", value: <strong>7</strong> }]} />);
    expect(screen.getByText("7").tagName).toBe("STRONG");
  });

  it("renders nothing but the list wrapper when items is empty", () => {
    const { container } = render(<MetadataList items={[]} />);
    expect(container.querySelector("dl")).toBeInTheDocument();
    expect(container.querySelector("dl")?.children).toHaveLength(0);
  });
});
