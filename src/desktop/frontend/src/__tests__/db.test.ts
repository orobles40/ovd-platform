import { describe, it, expect, vi, afterEach } from "vitest";
import { reportClientEvent } from "@/lib/ovd";

// ── reportClientEvent ─────────────────────────────────────────────────────────

describe("reportClientEvent", () => {
  afterEach(() => vi.restoreAllMocks());

  it("hace POST a /telemetry/client-event", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }) as Response,
    );
    await reportClientEvent("http://engine", "secret", {
      thread_id: "tid1",
      event: "cycle_completed",
      client: { qa_score: 90 },
    });
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://engine/telemetry/client-event",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("incluye X-OVD-Secret en el header", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }) as Response,
    );
    await reportClientEvent("http://engine", "my-secret", {
      thread_id: "tid2",
      event: "cycle_completed",
      client: {},
    });
    const [, opts] = fetchSpy.mock.calls[0];
    expect((opts as RequestInit).headers).toMatchObject({ "X-OVD-Secret": "my-secret" });
  });

  it("no propaga errores de red (fire-and-forget)", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("network"));
    await expect(
      reportClientEvent("http://engine", "s", { thread_id: "t", event: "e", client: {} }),
    ).resolves.toBeUndefined();
  });

  it("omite X-OVD-Secret cuando secret está vacío", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }) as Response,
    );
    await reportClientEvent("http://engine", "", {
      thread_id: "t",
      event: "e",
      client: {},
    });
    const [, opts] = fetchSpy.mock.calls[0];
    expect((opts as RequestInit).headers).not.toMatchObject({ "X-OVD-Secret": expect.anything() });
  });
});
