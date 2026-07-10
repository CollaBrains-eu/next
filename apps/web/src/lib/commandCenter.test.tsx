// apps/web/src/lib/commandCenter.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommandCenterStateProvider, useCommandCenterState } from "./commandCenter";

function Probe() {
  const { overlay, openPalette, setOverlay } = useCommandCenterState();
  return (
    <div>
      <span data-testid="overlay">{overlay}</span>
      <button onClick={openPalette}>open palette</button>
      <button onClick={() => setOverlay("none")}>close</button>
    </div>
  );
}

describe("CommandCenterStateProvider / useCommandCenterState", () => {
  it("starts closed", () => {
    render(
      <CommandCenterStateProvider>
        <Probe />
      </CommandCenterStateProvider>
    );
    expect(screen.getByTestId("overlay")).toHaveTextContent("none");
  });

  it("openPalette sets overlay to palette", () => {
    render(
      <CommandCenterStateProvider>
        <Probe />
      </CommandCenterStateProvider>
    );
    fireEvent.click(screen.getByText("open palette"));
    expect(screen.getByTestId("overlay")).toHaveTextContent("palette");
  });

  it("throws when used outside the provider", () => {
    function renderWithoutProvider() {
      render(<Probe />);
    }
    expect(renderWithoutProvider).toThrow("useCommandCenterState must be used within CommandCenterStateProvider");
  });
});
