import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBulkSelection } from "./useBulkSelection";

interface Doc {
  id: string;
  name: string;
}

const docA: Doc = { id: "a", name: "factuur.pdf" };
const docB: Doc = { id: "b", name: "notes.txt" };

describe("useBulkSelection", () => {
  it("starts with nothing selected", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isSelected(docA)).toBe(false);
  });

  it("toggle selects an item, and toggling again deselects it", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    expect(result.current.isSelected(docA)).toBe(true);
    expect(result.current.selectedCount).toBe(1);
    act(() => result.current.toggle(docA));
    expect(result.current.isSelected(docA)).toBe(false);
    expect(result.current.selectedCount).toBe(0);
  });

  it("tracks multiple selected items independently", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    act(() => result.current.toggle(docB));
    expect(result.current.selectedCount).toBe(2);
    expect(result.current.isSelected(docA)).toBe(true);
    expect(result.current.isSelected(docB)).toBe(true);
  });

  it("clear deselects everything", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    act(() => result.current.toggle(docB));
    act(() => result.current.clear());
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isSelected(docA)).toBe(false);
  });
});
