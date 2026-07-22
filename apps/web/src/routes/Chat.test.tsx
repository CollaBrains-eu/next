import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { LoadingBarProvider } from "../lib/loadingBar";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    chat: vi.fn(),
    submitFeedback: vi.fn(),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <LoadingBarProvider>
          <Chat />
        </LoadingBarProvider>
      </ToastProvider>
    </MemoryRouter>
  );
}

async function sendMessage(text: string) {
  fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("Chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.chat).mockResolvedValue({
      answer: "The contract expires in 2027.",
      citations: [{ marker: 1, document_id: "d1", document_title: "Lease Agreement", chunk_id: "c1" }],
      confidence: 90,
      sufficient_evidence: true,
    });
    vi.mocked(api.submitFeedback).mockResolvedValue(undefined);
  });

  it("shows the hint text before any messages are sent", () => {
    renderPage();
    expect(screen.getByText(/Ask a question about your documents/)).toBeInTheDocument();
  });

  it("sends a message and renders the assistant reply with a citation link", async () => {
    renderPage();
    await sendMessage("When does it expire?");
    expect(await screen.findByText("The contract expires in 2027.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("sends a message and renders the assistant reply when submitted via Enter in the textarea", async () => {
    renderPage();
    const input = screen.getByPlaceholderText("Ask a question…");
    fireEvent.change(input, { target: { value: "When does it expire?" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("The contract expires in 2027.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.chat).mockRejectedValue(new api.ApiError(500, "Chat boom"));
    renderPage();
    await sendMessage("hi");
    expect(await screen.findByText("Chat boom")).toBeInTheDocument();
  });

  it("disables the Send button while a request is in flight", async () => {
    let resolveChat: (v: api.ChatResponse) => void = () => {};
    vi.mocked(api.chat).mockReturnValue(new Promise((resolve) => { resolveChat = resolve; }));
    renderPage();
    await sendMessage("hi");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    resolveChat({ answer: "done", citations: [], confidence: null, sufficient_evidence: null });
    await screen.findByText("done");
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "another question" } });
    expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled();
  });

  it("shows the low-confidence badge when the response confidence is below the threshold", async () => {
    vi.mocked(api.chat).mockResolvedValue({
      answer: "Not sure about this.",
      citations: [],
      confidence: 30,
      sufficient_evidence: false,
    });
    renderPage();
    await sendMessage("hi");
    expect(await screen.findByText("Low confidence")).toBeInTheDocument();
  });

  it("submits feedback with the question/answer/reflection payload and shows a thanks toast", async () => {
    renderPage();
    await sendMessage("When does it expire?");
    await screen.findByText("The contract expires in 2027.");

    fireEvent.click(screen.getByLabelText("Good answer"));

    await waitFor(() =>
      expect(api.submitFeedback).toHaveBeenCalledWith({
        endpoint: "chat",
        question: "When does it expire?",
        answer: "The contract expires in 2027.",
        rating: "up",
        reflection_confidence: 90,
        reflection_sufficient_evidence: true,
      })
    );
    expect(await screen.findByText("Thanks for the feedback")).toBeInTheDocument();
  });

  it("clears a stale feedback-error banner once a vote succeeds", async () => {
    vi.mocked(api.submitFeedback).mockRejectedValueOnce(new api.ApiError(500, "boom")).mockResolvedValueOnce(undefined);
    renderPage();
    await sendMessage("When does it expire?");
    await screen.findByText("The contract expires in 2027.");

    fireEvent.click(screen.getByLabelText("Good answer"));
    expect(await screen.findByText("Couldn't submit feedback. Please try again.")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Good answer"));
    await waitFor(() => expect(screen.queryByText("Couldn't submit feedback. Please try again.")).not.toBeInTheDocument());
  });

  it("disables both thumbs buttons after a vote so a second vote can't be cast", async () => {
    renderPage();
    await sendMessage("When does it expire?");
    await screen.findByText("The contract expires in 2027.");

    fireEvent.click(screen.getByLabelText("Bad answer"));

    await waitFor(() => expect(screen.getByLabelText("Bad answer")).toBeDisabled());
    expect(screen.getByLabelText("Good answer")).toBeDisabled();
    expect(api.submitFeedback).toHaveBeenCalledTimes(1);
  });
});
