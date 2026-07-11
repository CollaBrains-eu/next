import { describe, expect, it, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CommandCenter } from "./CommandCenter";
import { CommandCenterStateProvider } from "../lib/commandCenter";

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
});
