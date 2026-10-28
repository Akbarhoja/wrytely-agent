import { describe, expect, it, vi } from "vitest";
import { forward } from "../lib/forward";

function dependencies() {
  return {
    configured: true,
    backend: "http://agent.internal:8000/",
    session: vi.fn(async () => ({
      userId: "user_alice",
      getToken: async () => "verified-session-token",
    })),
    fetch: vi.fn<typeof fetch>(async () =>
      Response.json({ task_id: "private-task", status: "ready" }, { status: 202 }),
    ),
  };
}
function request(path = "messages", method = "POST", origin = "https://agent.wrytely.io") {
  return new Request(`https://agent.wrytely.io/api/agent/${path}`, {
    method,
    headers: {
      Origin: origin,
      "Content-Type": "application/json",
      "Idempotency-Key": "stable-key",
      Authorization: "Bearer attacker-token",
      Cookie: "untrusted=anything",
      "X-User-Id": "user_bob",
    },
    body: method === "POST" ? JSON.stringify({ content: "Help me get started" }) : undefined,
  });
}
describe("authenticated API boundary", () => {
  it("forwards only the verified session and preserves retry identity", async () => {
    const deps = dependencies();
    const response = await forward(request(), ["messages"], deps);
    expect(response.status).toBe(202);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [url, options] = deps.fetch.mock.calls[0];
    expect(url).toBe("http://agent.internal:8000/v1/messages");
    const headers = new Headers(options?.headers);
    expect(headers.get("Authorization")).toBe("Bearer verified-session-token");
    expect(headers.get("Idempotency-Key")).toBe("stable-key");
    expect(headers.has("Cookie")).toBe(false);
    expect(headers.has("X-User-Id")).toBe(false);
    expect(options?.redirect).toBe("error");
  });
  it("rejects signed-out requests without calling the backend", async () => {
    const deps = dependencies();
    deps.session.mockResolvedValue({ userId: null as unknown as string, getToken: async () => "" });
    expect((await forward(request(), ["messages"], deps)).status).toBe(401);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it("rejects a session without a token", async () => {
    const deps = dependencies();
    deps.session.mockResolvedValue({
      userId: "user_alice",
      getToken: async () => null as unknown as string,
    });
    expect((await forward(request(), ["messages"], deps)).status).toBe(401);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it.each(["https://evil.example", "null", ""])(
    "rejects cross-origin mutation: %s",
    async (origin) => {
      const deps = dependencies();
      expect((await forward(request("messages", "POST", origin), ["messages"], deps)).status).toBe(
        403,
      );
      expect(deps.session).not.toHaveBeenCalled();
      expect(deps.fetch).not.toHaveBeenCalled();
    },
  );
  it("fails closed without configuration", async () => {
    const deps = dependencies();
    deps.configured = false;
    expect((await forward(request(), ["messages"], deps)).status).toBe(503);
    expect(deps.session).not.toHaveBeenCalled();
  });
  it.each([["../admin"], ["students", "user_bob"], ["tasks", "../../me"], ["healthz"]])(
    "does not expose arbitrary routes %s",
    async (...path) => {
      const deps = dependencies();
      expect((await forward(request(path.join("/"), "GET"), path, deps)).status).toBe(404);
      expect(deps.fetch).not.toHaveBeenCalled();
    },
  );
  it("preserves private-resource 404 without substituting success", async () => {
    const deps = dependencies();
    deps.fetch.mockResolvedValue(Response.json({ detail: "Task not found" }, { status: 404 }));
    const id = "00000000-0000-0000-0000-000000000000";
    expect((await forward(request(`tasks/${id}`, "GET"), ["tasks", id], deps)).status).toBe(404);
  });
  it("does not disclose upstream exceptions", async () => {
    const deps = dependencies();
    deps.fetch.mockRejectedValue(new Error("sensitive provider failure"));
    const response = await forward(request(), ["messages"], deps);
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("sensitive");
  });
});
