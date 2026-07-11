import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
