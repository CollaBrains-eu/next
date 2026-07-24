import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { CommandCenter } from "./CommandCenter";
import { CommandCenterStateProvider } from "../lib/commandCenter";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, search: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api.search).mockReset();
});

afterEach(cleanup);

function renderWithRouter() {
  return render(
    <MemoryRouter>
      <CommandCenterStateProvider>
        <CommandCenter />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("CommandCenter", () => {
  it("renders nothing visible by default", () => {
    renderWithRouter();
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("opens the command palette on Cmd+K", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("opens the shortcuts sheet on ? when not typing in a field", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "?" });
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
  });

  it("does not open the shortcuts sheet on ? while an input is focused", () => {
    render(
      <MemoryRouter>
        <CommandCenterStateProvider>
          <input aria-label="some field" />
          <CommandCenter />
        </CommandCenterStateProvider>
      </MemoryRouter>
    );
    screen.getByLabelText("some field").focus();
    fireEvent.keyDown(document.activeElement!, { key: "?" });
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("lists every NAV_ITEMS entry as a palette item, prefixed with 'Go to '", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByText("Go to Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
    expect(screen.getByText("Go to Settings")).toBeInTheDocument();
  });

  it("does not call search for a single-character query", async () => {
    vi.mocked(api.search).mockResolvedValue([]);
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "i" } });
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(api.search).not.toHaveBeenCalled();
  });

  it("calls search only after the debounce delay for a 2+ character query", async () => {
    vi.mocked(api.search).mockResolvedValue([
      { chunk_id: "c1", document_id: "d1", document_title: "Invoice.pdf", content: "Some content here", score: 0.9 },
    ]);
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "in" } });
    expect(api.search).not.toHaveBeenCalled();
    await waitFor(() => expect(api.search).toHaveBeenCalledWith("in", 5), { timeout: 1000 });
    expect(await screen.findByText("Invoice.pdf")).toBeInTheDocument();
  });

  it("discards a stale in-flight response when a newer query resolves first", async () => {
    let resolveFirst: (value: Awaited<ReturnType<typeof api.search>>) => void = () => {};
    const firstPromise = new Promise<Awaited<ReturnType<typeof api.search>>>((resolve) => {
      resolveFirst = resolve;
    });
    vi.mocked(api.search).mockImplementationOnce(() => firstPromise);
    vi.mocked(api.search).mockResolvedValueOnce([
      { chunk_id: "c2", document_id: "d2", document_title: "Contract.pdf", content: "Other content", score: 0.9 },
    ]);

    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    const input = screen.getByPlaceholderText(/search/i);

    fireEvent.change(input, { target: { value: "in" } });
    await waitFor(() => expect(api.search).toHaveBeenCalledTimes(1), { timeout: 1000 });

    await new Promise((resolve) => setTimeout(resolve, 350));
    fireEvent.change(input, { target: { value: "co" } });
    await waitFor(() => expect(api.search).toHaveBeenCalledTimes(2), { timeout: 1000 });
    expect(await screen.findByText("Contract.pdf")).toBeInTheDocument();

    act(() => {
      resolveFirst([
        { chunk_id: "c1", document_id: "d1", document_title: "Invoice.pdf", content: "Stale content", score: 0.9 },
      ]);
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText("Invoice.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("Contract.pdf")).toBeInTheDocument();
  });

  it("navigates to the document when a search result is selected", async () => {
    vi.mocked(api.search).mockResolvedValue([
      { chunk_id: "c1", document_id: "d1", document_title: "Invoice.pdf", content: "Some content", score: 0.9 },
    ]);
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "in" } });
    const result = await screen.findByText("Invoice.pdf", {}, { timeout: 1000 });
    fireEvent.click(result);
    await waitFor(() => expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument());
  });
});
