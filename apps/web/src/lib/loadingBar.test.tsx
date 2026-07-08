import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LoadingBarProvider, useLoadingBar } from "./loadingBar";

function Trigger() {
  const { start, done } = useLoadingBar();
  return (
    <>
      <button onClick={start}>start</button>
      <button onClick={done}>done</button>
    </>
  );
}

describe("loading bar", () => {
  it("is not visible (0 width) before start is called", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    const bar = screen.getByTestId("loading-bar");
    expect(bar).toHaveStyle({ width: "0%" });
  });

  it("becomes visible with nonzero width after start", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    fireEvent.click(screen.getByText("start"));
    const bar = screen.getByTestId("loading-bar");
    expect(bar).not.toHaveStyle({ width: "0%" });
  });

  it("goes to 100% width after done", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    fireEvent.click(screen.getByText("start"));
    fireEvent.click(screen.getByText("done"));
    const bar = screen.getByTestId("loading-bar");
    expect(bar).toHaveStyle({ width: "100%" });
  });

  it("throws a clear error if useLoadingBar is called outside the provider", () => {
    function Orphan() {
      useLoadingBar();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow("useLoadingBar must be used within a LoadingBarProvider");
  });
});
