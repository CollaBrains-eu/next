import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Entities from "./Entities";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
  };
});

const ENTITIES: api.EntityOut[] = [
  { id: "e1", name: "Jane Smith", entity_type: "person", created_at: "2026-01-01T00:00:00Z" },
  { id: "e2", name: "Acme Corp", entity_type: "organization", created_at: "2026-01-02T00:00:00Z" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Entities />
    </MemoryRouter>
  );
}

describe("Entities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listEntities).mockResolvedValue(ENTITIES);
  });

  it("renders entities with their type badge", async () => {
    renderPage();
    expect(await screen.findByText("Jane Smith")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("person")).toBeInTheDocument();
    expect(screen.getByText("organization")).toBeInTheDocument();
  });

  it("shows an empty message when there are no entities", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No entities found.")).toBeInTheDocument();
  });

  it("re-queries listEntities when the search box changes", async () => {
    renderPage();
    await screen.findByText("Jane Smith");
    fireEvent.change(screen.getByPlaceholderText("Search entities…"), { target: { value: "Jane" } });
    await waitFor(() => expect(api.listEntities).toHaveBeenLastCalledWith("Jane", undefined));
  });

  it("re-queries listEntities when the type filter changes", async () => {
    renderPage();
    await screen.findByText("Jane Smith");
    fireEvent.change(screen.getByDisplayValue("All types"), { target: { value: "person" } });
    await waitFor(() => expect(api.listEntities).toHaveBeenLastCalledWith(undefined, "person"));
  });
});
