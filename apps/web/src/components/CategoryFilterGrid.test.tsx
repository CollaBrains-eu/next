import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CategoryFilterGrid } from "./CategoryFilterGrid";
import type { CategoryOut } from "../lib/api";

const categories: CategoryOut[] = [
  { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
  { id: "cat-payslip", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
  { id: "cat-invoice", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
  { id: "parent-other", slug: "other_group", icon: "Inbox", color: "#8E8E93", parent_id: null },
  { id: "cat-other-docs", slug: "other_documents", icon: "File", color: "#8E8E93", parent_id: "parent-other" },
];

describe("CategoryFilterGrid", () => {
  it("renders a group header per parent category and a chip per child", () => {
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={() => {}} onToggleChild={() => {}} />
    );

    expect(screen.getByRole("button", { name: /finance/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Payslip & Salary" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Invoices" })).toBeInTheDocument();
  });

  it("calls onToggleChild with the child's id when a child chip is clicked", () => {
    const onToggleChild = vi.fn();
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={() => {}} onToggleChild={onToggleChild} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Payslip & Salary" }));
    expect(onToggleChild).toHaveBeenCalledWith("cat-payslip");
  });

  it("calls onToggleGroup with all child ids when a group header is clicked", () => {
    const onToggleGroup = vi.fn();
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={onToggleGroup} onToggleChild={() => {}} />
    );

    fireEvent.click(screen.getByRole("button", { name: /finance/i }));
    expect(onToggleGroup).toHaveBeenCalledWith(["cat-payslip", "cat-invoice"]);
  });
});
