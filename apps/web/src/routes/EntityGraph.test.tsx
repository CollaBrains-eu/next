import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EntityGraph from "./EntityGraph";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getEntityGraph: vi.fn(),
  };
});

const GRAPH: api.EntityGraphOut = {
  center: { id: "e1", name: "Jane Smith", entity_type: "person" },
  nodes: [{ id: "e2", name: "Acme Corp", entity_type: "organization" }],
  edges: [{ source: "e1", target: "e2", relationship_type: "works at", document_id: null }],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/entities/e1"]}>
      <Routes>
        <Route path="/entities/:id" element={<EntityGraph />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("EntityGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getEntityGraph).mockResolvedValue(GRAPH);
  });

  it("renders the center entity name and relationship count", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Jane Smith" })).toBeInTheDocument();
    expect(screen.getByText("Person · 1 direct relationship")).toBeInTheDocument();
  });

  it("renders related node names", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Jane Smith" });
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
  });

  it("shows an empty message when there are no relationships", async () => {
    vi.mocked(api.getEntityGraph).mockResolvedValue({ ...GRAPH, nodes: [], edges: [] });
    renderPage();
    expect(await screen.findByText("No known relationships for this entity yet.")).toBeInTheDocument();
  });

  it("shows an error message on failure", async () => {
    vi.mocked(api.getEntityGraph).mockRejectedValue(new api.ApiError(500, "Graph boom"));
    renderPage();
    expect(await screen.findByText("Graph boom")).toBeInTheDocument();
  });
});
