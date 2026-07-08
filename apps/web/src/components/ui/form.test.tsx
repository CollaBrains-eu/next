import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TextField, Select, Checkbox, Switch } from "./form";

describe("TextField", () => {
  it("renders the label and current value", () => {
    render(<TextField label="Case title" value="Claim #4471" onChange={() => {}} />);
    expect(screen.getByLabelText("Case title")).toHaveValue("Claim #4471");
  });

  it("calls onChange with the new value", () => {
    const onChange = vi.fn();
    render(<TextField label="Case title" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Case title"), { target: { value: "New title" } });
    expect(onChange).toHaveBeenCalledWith("New title");
  });

  it("shows an error message and error styling when error is set", () => {
    render(<TextField label="Case title" value="" onChange={() => {}} error="Case title is required" />);
    expect(screen.getByText("Case title is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Case title")).toHaveClass("border-danger");
  });

  it("renders no error message when error is unset", () => {
    render(<TextField label="Case title" value="x" onChange={() => {}} />);
    expect(screen.queryByText(/required/)).not.toBeInTheDocument();
  });
});

describe("Select", () => {
  it("renders all options and the selected value", () => {
    render(<Select label="Case type" value="Legal matter" onChange={() => {}} options={["Insurance claim", "Legal matter"]} />);
    expect(screen.getByLabelText("Case type")).toHaveValue("Legal matter");
    expect(screen.getByText("Insurance claim")).toBeInTheDocument();
  });

  it("calls onChange with the new value", () => {
    const onChange = vi.fn();
    render(<Select label="Case type" value="Insurance claim" onChange={onChange} options={["Insurance claim", "Legal matter"]} />);
    fireEvent.change(screen.getByLabelText("Case type"), { target: { value: "Legal matter" } });
    expect(onChange).toHaveBeenCalledWith("Legal matter");
  });
});

describe("Checkbox", () => {
  it("reflects the checked prop and calls onChange on toggle", () => {
    const onChange = vi.fn();
    render(<Checkbox label="Notify assignee" checked={true} onChange={onChange} />);
    const checkbox = screen.getByLabelText("Notify assignee");
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(false);
  });
});

describe("Switch", () => {
  it("reflects the checked prop and calls onChange on toggle", () => {
    const onChange = vi.fn();
    render(<Switch label="Auto-archive when closed" checked={false} onChange={onChange} />);
    const toggle = screen.getByLabelText("Auto-archive when closed");
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
