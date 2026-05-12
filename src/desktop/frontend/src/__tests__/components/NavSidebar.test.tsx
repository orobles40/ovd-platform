import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NavSidebar } from "@/components/NavSidebar";

const NAV_COLLAPSED_KEY = "ovd_nav_collapsed";

function renderSidebar(collapsed: boolean, onToggle = vi.fn(), email?: string) {
  return render(
    <MemoryRouter initialEntries={["/workspace"]}>
      <NavSidebar collapsed={collapsed} onToggle={onToggle} email={email} />
    </MemoryRouter>
  );
}

describe("NavSidebar — expandido", () => {
  it("muestra las etiquetas de los ítems", () => {
    renderSidebar(false);
    expect(screen.getByText("Lanzar FR")).toBeInTheDocument();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
  });

  it("muestra el email cuando se proporciona", () => {
    renderSidebar(false, vi.fn(), "omar@codigonet.cloud");
    expect(screen.getByText("omar@codigonet.cloud")).toBeInTheDocument();
  });

  it("muestra el botón de colapsar (ChevronLeft)", () => {
    renderSidebar(false);
    expect(screen.getByTitle("Colapsar menú")).toBeInTheDocument();
  });
});

describe("NavSidebar — colapsado", () => {
  it("no muestra etiquetas de texto", () => {
    renderSidebar(true);
    expect(screen.queryByText("Lanzar FR")).not.toBeInTheDocument();
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
  });

  it("muestra el botón de expandir (ChevronRight)", () => {
    renderSidebar(true);
    expect(screen.getByTitle("Expandir menú")).toBeInTheDocument();
  });
});

describe("NavSidebar — toggle", () => {
  it("llama onToggle al hacer click en el botón", () => {
    const onToggle = vi.fn();
    renderSidebar(false, onToggle);
    fireEvent.click(screen.getByTitle("Colapsar menú"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("persiste estado colapsado en localStorage", () => {
    localStorage.setItem(NAV_COLLAPSED_KEY, "true");
    expect(localStorage.getItem(NAV_COLLAPSED_KEY)).toBe("true");
  });
});

describe("NavSidebar — iniciales avatar", () => {
  it("muestra iniciales del email", () => {
    renderSidebar(false, vi.fn(), "omar@codigonet.cloud");
    expect(screen.getByText("OM")).toBeInTheDocument();
  });

  it("muestra OV si no hay email", () => {
    renderSidebar(false);
    expect(screen.getByText("OV")).toBeInTheDocument();
  });
});
