import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UploadDialog from "./UploadDialog";
import { ApiError } from "../lib/api";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, uploadDocument: vi.fn() };
});

describe("UploadDialog", () => {
  it("shows the upload button collapsed by default", () => {
    render(<UploadDialog onUploaded={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Upload document" })).toBeInTheDocument();
  });

  it("expands to the file picker when clicked", () => {
    render(<UploadDialog onUploaded={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(screen.getByText("Upload a document")).toBeInTheDocument();
  });

  it("uploads the selected file and calls onUploaded", async () => {
    vi.mocked(api.uploadDocument).mockResolvedValue({} as api.DocumentOut);
    const onUploaded = vi.fn();
    render(<UploadDialog onUploaded={onUploaded} />);
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    const file = new File(["hello"], "note.txt", { type: "text/plain" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadDocument).toHaveBeenCalledWith(file));
    await waitFor(() => expect(onUploaded).toHaveBeenCalled());
  });

  it("shows an error message when upload fails", async () => {
    vi.mocked(api.uploadDocument).mockRejectedValue(new ApiError(500, "Upload failed"));
    render(<UploadDialog onUploaded={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    const file = new File(["hello"], "note.txt", { type: "text/plain" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText("Upload failed")).toBeInTheDocument();
  });
});
