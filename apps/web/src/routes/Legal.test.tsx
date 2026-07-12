import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Legal from "./Legal";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    legalDraft: vi.fn(),
    listDocuments: vi.fn(),
  };
});

const DOCS: api.DocumentOut[] = [
  { id: "d1", title: "Lease Agreement" } as api.DocumentOut,
  { id: "d2", title: "Evidence letter" } as api.DocumentOut,
];

function renderPage() {
  return render(
    <MemoryRouter>
      <LoadingBarProvider>
        <Legal />
      </LoadingBarProvider>
    </MemoryRouter>
  );
}

describe("Legal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDocuments).mockResolvedValue(DOCS);
    vi.mocked(api.legalDraft).mockResolvedValue({
      draft: "Dear Sir or Madam, ...",
      citations: [{ marker: 1, document_id: "d1", document_title: "Lease Agreement", chunk_id: "c1" }],
      disclaimer: "This draft is not legal advice.",
    });
  });

  it("lists documents in the scope combobox once loaded", async () => {
    renderPage();
    await screen.findByText("Scope to documents (optional)");
    fireEvent.click(screen.getByPlaceholderText("Search…"));
    expect(screen.getByRole("button", { name: "Lease Agreement" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evidence letter" })).toBeInTheDocument();
  });

  it("drafts and renders the result with disclaimer and citation", async () => {
    renderPage();
    await screen.findByText("Scope to documents (optional)");
    fireEvent.click(screen.getByPlaceholderText("Search…"));
    fireEvent.click(screen.getByRole("button", { name: "Lease Agreement" }));
    fireEvent.change(screen.getByPlaceholderText(/Draft a letter/), { target: { value: "Summarize the lease." } });
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(api.legalDraft).toHaveBeenCalledWith("Summarize the lease.", ["d1"]));
    expect(await screen.findByText("Dear Sir or Madam, ...")).toBeInTheDocument();
    expect(screen.getByText("This draft is not legal advice.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.legalDraft).mockRejectedValue(new api.ApiError(500, "Draft boom"));
    renderPage();
    await screen.findByText("Scope to documents (optional)");
    fireEvent.change(screen.getByPlaceholderText(/Draft a letter/), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    expect(await screen.findByText("Draft boom")).toBeInTheDocument();
  });
});
