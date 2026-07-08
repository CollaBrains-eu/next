import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { DataTable, type Column } from "./DataTable";

interface Row {
  id: string;
  plate: string;
  make: string;
}

const columns: Column<Row>[] = [
  { key: "plate", header: "Plate", sortable: true, sortValue: (r) => r.plate, render: (r) => r.plate },
  { key: "make", header: "Make", sortable: true, sortValue: (r) => r.make, render: (r) => r.make },
];

function makeRows(n: number): Row[] {
  return Array.from({ length: n }, (_, i) => ({ id: String(i), plate: `PLATE-${String(i).padStart(2, "0")}`, make: `Make ${i}` }));
}

describe("DataTable", () => {
  it("renders column headers and row cells", () => {
    render(<DataTable columns={columns} rows={makeRows(3)} rowKey={(r) => r.id} />);
    expect(screen.getByText("Plate")).toBeInTheDocument();
    expect(screen.getByText("PLATE-00")).toBeInTheDocument();
  });

  it("paginates: only pageSize rows show, and page buttons appear", () => {
    render(<DataTable columns={columns} rows={makeRows(25)} pageSize={10} rowKey={(r) => r.id} />);
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10);
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
  });

  it("clicking a page button shows that page's rows", () => {
    render(<DataTable columns={columns} rows={makeRows(25)} pageSize={10} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: "2" }));
    expect(screen.getByText("PLATE-10")).toBeInTheDocument();
    expect(screen.queryByText("PLATE-00")).not.toBeInTheDocument();
  });

  it("clicking a sortable header sorts the rows ascending, then descending on a second click", () => {
    const rows = [
      { id: "1", plate: "B", make: "X" },
      { id: "2", plate: "A", make: "Y" },
      { id: "3", plate: "C", make: "Z" },
    ];
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByText("Plate"));
    const cellsAsc = within(screen.getAllByRole("row")[1]).getByText("A");
    expect(cellsAsc).toBeInTheDocument();
    fireEvent.click(screen.getByText("Plate"));
    const cellsDesc = within(screen.getAllByRole("row")[1]).getByText("C");
    expect(cellsDesc).toBeInTheDocument();
  });

  it("does not attach a sort handler to a non-sortable column", () => {
    const nonSortableColumns: Column<Row>[] = [{ key: "plate", header: "Plate", render: (r) => r.plate }];
    render(<DataTable columns={nonSortableColumns} rows={makeRows(3)} rowKey={(r) => r.id} />);
    const header = screen.getByText("Plate");
    expect(header.closest("th")).not.toHaveClass("cursor-pointer");
  });
});
