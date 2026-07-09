import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Avatar, AvatarGroup } from "./Avatar";

describe("Avatar", () => {
  it("renders initials from a two-word name", () => {
    render(<Avatar name="Jane Doe" />);
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  it("renders a single initial from a one-word name", () => {
    render(<Avatar name="Cher" />);
    expect(screen.getByText("C")).toBeInTheDocument();
  });

  it("is deterministic: same name always gets the same background color", () => {
    const { container: a } = render(<Avatar name="Jane Doe" />);
    const { container: b } = render(<Avatar name="Jane Doe" />);
    expect((a.firstChild as HTMLElement).style.backgroundColor).toBe(
      (b.firstChild as HTMLElement).style.backgroundColor,
    );
  });
});

describe("AvatarGroup", () => {
  it("renders an overflow badge when there are more names than max", () => {
    render(<AvatarGroup names={["A B", "C D", "E F", "G H", "I J"]} max={3} />);
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("renders no overflow badge when names fit within max", () => {
    render(<AvatarGroup names={["A B", "C D"]} max={3} />);
    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });
});
