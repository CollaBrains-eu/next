import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import MobileTabBar from "./MobileTabBar";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<MobileTabBar />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("MobileTabBar", () => {
  it("renders the four primary destinations and the upload FAB", () => {
    renderAt("/");
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
    expect(screen.getByText("Dossiers")).toBeInTheDocument();
    expect(screen.getByText("Acties")).toBeInTheDocument();
    expect(screen.getByLabelText("Upload a document")).toBeInTheDocument();
  });

  it("marks Home as active on the root route", () => {
    renderAt("/");
    expect(screen.getByText("Home").closest("a")).toHaveClass("text-accent");
  });

  it("does not mark Home as active on other routes", () => {
    renderAt("/documents");
    expect(screen.getByText("Home").closest("a")).not.toHaveClass("text-accent");
  });

  it("marks Docs as active on the documents route", () => {
    renderAt("/documents");
    expect(screen.getByText("Docs").closest("a")).toHaveClass("text-accent");
  });

  it("marks Dossiers as active on nested case routes", () => {
    renderAt("/cases/abc-123");
    expect(screen.getByText("Dossiers").closest("a")).toHaveClass("text-accent");
  });

  it("the FAB links to the documents page", () => {
    renderAt("/");
    expect(screen.getByLabelText("Upload a document").closest("a")).toHaveAttribute("href", "/documents");
  });
});
