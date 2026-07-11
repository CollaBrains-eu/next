import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPipeline } from "./StatusPipeline";

describe("StatusPipeline", () => {
  const stages = [
    { key: "open", label: "open" },
    { key: "closed", label: "closed" },
  ];

  it("renders every stage label", () => {
    render(<StatusPipeline stages={stages} currentKey="open" />);
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("does not crash on an unknown currentKey", () => {
    render(<StatusPipeline stages={stages} currentKey="archived" />);
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("renders a three-stage pipeline with the middle stage current", () => {
    const taskStages = [
      { key: "open", label: "To do" },
      { key: "in_progress", label: "In progress" },
      { key: "done", label: "Done" },
    ];
    render(<StatusPipeline stages={taskStages} currentKey="in_progress" />);
    expect(screen.getByText("To do")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
});
