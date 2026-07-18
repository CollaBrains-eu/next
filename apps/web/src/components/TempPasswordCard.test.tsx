import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TempPasswordCard } from "./TempPasswordCard";

describe("TempPasswordCard", () => {
  it("renders the message and password, and calls onDismiss", () => {
    const onDismiss = vi.fn();
    render(<TempPasswordCard message="User bob created." password="a-temp-pw" onDismiss={onDismiss} />);

    expect(screen.getByText("User bob created.")).toBeInTheDocument();
    expect(screen.getByTestId("temp-password")).toHaveTextContent("a-temp-pw");

    fireEvent.click(screen.getByRole("button"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
