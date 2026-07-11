import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DashboardWidgetCard } from "./DashboardWidgetCard";

describe("DashboardWidgetCard", () => {
  it("renders the title and children when loaded and non-empty", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByText("Recent documents")).toBeInTheDocument();
    expect(screen.getByText("Lease agreement")).toBeInTheDocument();
  });

  it("shows a skeleton instead of children while loading", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={true} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByTestId("widget-skeleton")).toBeInTheDocument();
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
  });

  it("shows the empty message when loaded and empty", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={true} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
  });

  it("collapses and expands when the toggle is clicked, hiding content while collapsed", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    const toggle = screen.getByRole("button", { name: "Collapse Recent documents" });
    fireEvent.click(toggle);
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand Recent documents" }));
    expect(screen.getByText("Lease agreement")).toBeInTheDocument();
  });

  it("renders optional header actions", () => {
    render(
      <DashboardWidgetCard
        title="Recent documents"
        loading={false}
        isEmpty={false}
        emptyMessage="Nothing here"
        actions={<a href="/documents">View all</a>}
      >
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByRole("link", { name: "View all" })).toBeInTheDocument();
  });
});
