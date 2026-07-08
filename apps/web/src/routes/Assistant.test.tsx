import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Assistant from "./Assistant";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    askManager: vi.fn(),
  };
});

function renderPage() {
  return render(
    <LoadingBarProvider>
      <Assistant />
    </LoadingBarProvider>
  );
}

describe("Assistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.askManager).mockResolvedValue({ answer: "I created the case.", tool_called: "create_case" });
  });

  it("shows the hint text before any messages are sent", () => {
    renderPage();
    expect(screen.getByText(/Ask the assistant to do something/)).toBeInTheDocument();
  });

  it("sends a message and renders the assistant reply with the tool it called", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask the assistant…"), { target: { value: "Create a case for Smith" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("I created the case.")).toBeInTheDocument();
    expect(screen.getByText("via: create_case")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.askManager).mockRejectedValue(new api.ApiError(500, "Assistant boom"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask the assistant…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Assistant boom")).toBeInTheDocument();
  });
});
