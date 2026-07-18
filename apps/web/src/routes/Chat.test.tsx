import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    chat: vi.fn(),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <LoadingBarProvider>
        <Chat />
      </LoadingBarProvider>
    </MemoryRouter>
  );
}

describe("Chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.chat).mockResolvedValue({
      answer: "The contract expires in 2027.",
      citations: [{ marker: 1, document_id: "d1", document_title: "Lease Agreement", chunk_id: "c1" }],
    });
  });

  it("shows the hint text before any messages are sent", () => {
    renderPage();
    expect(screen.getByText(/Ask a question about your documents/)).toBeInTheDocument();
  });

  it("sends a message and renders the assistant reply with a citation link", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "When does it expire?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("The contract expires in 2027.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.chat).mockRejectedValue(new api.ApiError(500, "Chat boom"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Chat boom")).toBeInTheDocument();
  });

  it("disables the Send button while a request is in flight", async () => {
    let resolveChat: (v: api.ChatResponse) => void = () => {};
    vi.mocked(api.chat).mockReturnValue(new Promise((resolve) => { resolveChat = resolve; }));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    resolveChat({ answer: "done", citations: [] });
    await screen.findByText("done");
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "another question" } });
    expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled();
  });
});
