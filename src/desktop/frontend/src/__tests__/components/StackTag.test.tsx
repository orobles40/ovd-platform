import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

function StackTag({ stack }: { stack?: string }) {
  if (!stack) return null;
  return (
    <span data-testid="stack-tag">
      {stack}
    </span>
  );
}

describe("StackTag", () => {
  it("no renderiza nada si stack es undefined", () => {
    const { container } = render(<StackTag />);
    expect(container.firstChild).toBeNull();
  });

  it("no renderiza nada si stack es string vacío", () => {
    const { container } = render(<StackTag stack="" />);
    expect(container.firstChild).toBeNull();
  });

  it("muestra el stack cuando está definido", () => {
    render(<StackTag stack="Python/FastAPI" />);
    expect(screen.getByTestId("stack-tag")).toHaveTextContent("Python/FastAPI");
  });

  it("muestra stack con Oracle", () => {
    render(<StackTag stack="Python/FastAPI/Oracle12+" />);
    expect(screen.getByTestId("stack-tag")).toHaveTextContent("Python/FastAPI/Oracle12+");
  });
});
