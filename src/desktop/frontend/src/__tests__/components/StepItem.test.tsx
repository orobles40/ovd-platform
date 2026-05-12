import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

type StepStatus = "pending" | "active" | "done" | "error";

interface PipelineStep { id: string; label: string; nodes: string[] }

function StepItem({ step, status }: { step: PipelineStep; status: StepStatus; isLast: boolean }) {
  return (
    <div data-testid={`step-${step.id}`} data-status={status}>
      <span>{step.label}</span>
      {status === "done"   && <span data-testid="icon-done" />}
      {status === "active" && <span data-testid="icon-active" />}
      {status === "error"  && <span data-testid="icon-error" />}
    </div>
  );
}

const step: PipelineStep = { id: "qa", label: "QA Review", nodes: ["qa_review"] };

describe("StepItem", () => {
  it("muestra la etiqueta del paso", () => {
    render(<StepItem step={step} status="pending" isLast={false} />);
    expect(screen.getByText("QA Review")).toBeInTheDocument();
  });

  it("muestra icono done cuando status=done", () => {
    render(<StepItem step={step} status="done" isLast={false} />);
    expect(screen.getByTestId("icon-done")).toBeInTheDocument();
  });

  it("muestra icono active cuando status=active", () => {
    render(<StepItem step={step} status="active" isLast={false} />);
    expect(screen.getByTestId("icon-active")).toBeInTheDocument();
  });

  it("muestra icono error cuando status=error", () => {
    render(<StepItem step={step} status="error" isLast={false} />);
    expect(screen.getByTestId("icon-error")).toBeInTheDocument();
  });

  it("no muestra iconos cuando status=pending", () => {
    render(<StepItem step={step} status="pending" isLast={false} />);
    expect(screen.queryByTestId("icon-done")).not.toBeInTheDocument();
    expect(screen.queryByTestId("icon-active")).not.toBeInTheDocument();
    expect(screen.queryByTestId("icon-error")).not.toBeInTheDocument();
  });
});
