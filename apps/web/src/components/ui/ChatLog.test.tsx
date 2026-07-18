import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatLog } from "./ChatLog";

describe("ChatLog", () => {
  it("shows the hint and no bubbles when there are no turns", () => {
    render(<ChatLog turns={[]} sending={false} hint="Ask something" thinkingLabel="Thinking" />);
    expect(screen.getByText("Ask something")).toBeInTheDocument();
  });

  it("renders each turn's content and an optional footer", () => {
    render(
      <ChatLog
        turns={[
          { role: "user", content: "What's the status?" },
          { role: "assistant", content: "It's ready.", footer: <span>source: doc.pdf</span> },
        ]}
        sending={false}
        thinkingLabel="Thinking"
      />,
    );
    expect(screen.getByText("What's the status?")).toBeInTheDocument();
    expect(screen.getByText("It's ready.")).toBeInTheDocument();
    expect(screen.getByText("source: doc.pdf")).toBeInTheDocument();
  });

  it("shows an accessible typing indicator while sending, with no visible text", () => {
    render(<ChatLog turns={[{ role: "user", content: "hi" }]} sending thinkingLabel="Thinking…" />);
    expect(screen.getByRole("status", { name: "Thinking…" })).toBeInTheDocument();
  });

  it("does not show the typing indicator once a reply has arrived", () => {
    render(
      <ChatLog
        turns={[{ role: "user", content: "hi" }, { role: "assistant", content: "hello" }]}
        sending={false}
        thinkingLabel="Thinking…"
      />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows the low-confidence badge only when confidence is below the threshold", () => {
    const { rerender } = render(
      <ChatLog
        turns={[{ role: "assistant", content: "hello", confidence: 80 }]}
        sending={false}
        thinkingLabel="Thinking"
        lowConfidenceLabel="Low confidence"
      />,
    );
    expect(screen.queryByText("Low confidence")).not.toBeInTheDocument();

    rerender(
      <ChatLog
        turns={[{ role: "assistant", content: "hello", confidence: 40 }]}
        sending={false}
        thinkingLabel="Thinking"
        lowConfidenceLabel="Low confidence"
      />,
    );
    expect(screen.getByText("Low confidence")).toBeInTheDocument();
  });

  it("calls onFeedback with the right rating and disables both buttons after voting", () => {
    const onFeedback = vi.fn();
    render(
      <ChatLog
        turns={[{ role: "assistant", content: "hello", onFeedback, feedbackGiven: null }]}
        sending={false}
        thinkingLabel="Thinking"
        thumbsUpLabel="Good answer"
        thumbsDownLabel="Bad answer"
      />,
    );
    fireEvent.click(screen.getByLabelText("Good answer"));
    expect(onFeedback).toHaveBeenCalledWith("up");
  });

  it("disables both thumbs buttons once feedbackGiven is set", () => {
    render(
      <ChatLog
        turns={[{ role: "assistant", content: "hello", onFeedback: vi.fn(), feedbackGiven: "down" }]}
        sending={false}
        thinkingLabel="Thinking"
        thumbsUpLabel="Good answer"
        thumbsDownLabel="Bad answer"
      />,
    );
    expect(screen.getByLabelText("Good answer")).toBeDisabled();
    expect(screen.getByLabelText("Bad answer")).toBeDisabled();
    expect(screen.getByLabelText("Bad answer")).toHaveAttribute("aria-pressed", "true");
  });

  it("does not render thumbs buttons for user turns even if onFeedback is somehow set", () => {
    render(
      <ChatLog
        turns={[{ role: "user", content: "hi" }]}
        sending={false}
        thinkingLabel="Thinking"
        thumbsUpLabel="Good answer"
        thumbsDownLabel="Bad answer"
      />,
    );
    expect(screen.queryByLabelText("Good answer")).not.toBeInTheDocument();
  });
});
