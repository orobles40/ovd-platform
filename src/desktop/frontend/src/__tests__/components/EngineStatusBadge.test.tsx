import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

function EngineStatusBadge({ url }: { url: string }) {
  const [status, setStatus] = React.useState<"checking" | "up" | "down">("checking");

  React.useEffect(() => {
    if (!url) { setStatus("down"); return; }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 3000);
    fetch(`${url}/health`, { signal: ctrl.signal })
      .then((r) => setStatus(r.ok ? "up" : "down"))
      .catch(() => setStatus("down"))
      .finally(() => clearTimeout(timer));
  }, [url]);

  return <span data-testid="badge" data-status={status}>{status}</span>;
}

import React from "react";

describe("EngineStatusBadge", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("muestra 'checking' inicialmente", () => {
    vi.spyOn(global, "fetch").mockReturnValue(new Promise(() => {}));
    render(<EngineStatusBadge url="http://localhost:8001" />);
    expect(screen.getByTestId("badge")).toHaveAttribute("data-status", "checking");
  });

  it("muestra 'up' cuando el engine responde 200", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 200 }) as Response);
    render(<EngineStatusBadge url="http://localhost:8001" />);
    await waitFor(() =>
      expect(screen.getByTestId("badge")).toHaveAttribute("data-status", "up")
    );
  });

  it("muestra 'down' cuando el engine falla", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("network error"));
    render(<EngineStatusBadge url="http://localhost:8001" />);
    await waitFor(() =>
      expect(screen.getByTestId("badge")).toHaveAttribute("data-status", "down")
    );
  });

  it("muestra 'down' si url está vacía", async () => {
    render(<EngineStatusBadge url="" />);
    await waitFor(() =>
      expect(screen.getByTestId("badge")).toHaveAttribute("data-status", "down")
    );
  });

  it("muestra 'down' cuando el engine responde 500", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 500 }) as Response);
    render(<EngineStatusBadge url="http://localhost:8001" />);
    await waitFor(() =>
      expect(screen.getByTestId("badge")).toHaveAttribute("data-status", "down")
    );
  });
});
