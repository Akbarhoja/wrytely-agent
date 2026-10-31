import { describe, expect, it, vi } from "vitest";
import { forward } from "../lib/forward";

const uuid = "00000000-0000-4000-8000-000000000001";
const base = "https://agent.example";
const paths = [
  ["POST", ["source-connections", "canvas", "pairing"]],
  ["GET", ["source-connections", uuid]],
  ["POST", ["source-connections", uuid, "revoke"]],
] as const;

function dependencies() {
  return {
    configured: true,
    backend: "https://backend.example/",
    session: vi.fn(async () => ({ userId: "alice", getToken: async () => "verified" })),
    fetch: vi.fn<typeof fetch>(async () => Response.json({ state: "pending_identity" })),
  };
}

function request(path: readonly string[], method = "POST", origin = base, body = "{}") {
  return new Request(`${base}/api/agent/${path.join("/")}?user_id=bob`, {
    method,
    headers: {
      Origin: origin,
      "Content-Type": "application/json",
      Authorization: "Bearer browser",
      Cookie: "PRIVATE_COOKIE",
      "X-User-Id": "bob",
      "Idempotency-Key": "stable",
    },
    body: method === "POST" ? body : undefined,
  });
}

describe("private Canvas lifecycle proxy", () => {
  it.each(paths)("forwards only verified authority for %s %j", async (method, path) => {
    const deps = dependencies();
    const result = await forward(request(path, method), [...path], deps);
    expect(result.status).toBe(200);
    expect(result.headers.get("cache-control")).toBe("no-store");
    const [url, init] = deps.fetch.mock.calls[0];
    expect(url).toBe(`https://backend.example/v1/${path.join("/")}`);
    const headers = new Headers(init?.headers);
    expect(headers.get("authorization")).toBe("Bearer verified");
    expect(headers.get("cookie")).toBeNull();
    expect(headers.get("x-user-id")).toBeNull();
    expect(init?.cache).toBe("no-store");
    expect(init?.redirect).toBe("error");
  });

  it.each(paths)("requires a signed-in session for %s %j", async (method, path) => {
    const deps = dependencies();
    deps.session.mockResolvedValue({ userId: "", getToken: async () => "" });
    const result = await forward(request(path, method), [...path], deps);
    expect(result.status).toBe(401);
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it.each(["pairing", "revoke"])("blocks cross-origin %s", async (action) => {
    const path = action === "pairing" ? paths[0][1] : paths[2][1];
    const deps = dependencies();
    expect(
      (await forward(request(path, "POST", "https://other.example"), [...path], deps)).status,
    ).toBe(403);
    expect(deps.session).not.toHaveBeenCalled();
  });

  it.each([
    ["POST", ["source-connections", "canvas", "redeem"]],
    ["POST", ["source-connections", "canvas", "bind"]],
    ["POST", ["source-connections", "canvas", "sync"]],
    ["GET", ["source-connections"]],
    ["GET", ["source-connections", "not-a-uuid"]],
    ["GET", ["source-connections", "..", uuid]],
    ["POST", ["source-connections/canvas", "pairing"]],
    ["GET", [`source-connections/${uuid}`]],
    ["POST", ["source-connections", `${uuid}/revoke`]],
    ["GET", ["source-connections", "canvas", "pairing"]],
    ["POST", ["source-connections", uuid]],
    ["GET", ["source-connections", uuid, "revoke"]],
    ["DELETE", ["source-connections", uuid]],
  ] as const)("rejects unsupported or disguised route %s %j", async (method, path) => {
    const deps = dependencies();
    expect((await forward(request(path, method), [...path], deps)).status).toBe(404);
    expect(deps.session).not.toHaveBeenCalled();
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("rejects streamed overflow before forwarding, including lying lengths", async () => {
    const deps = dependencies();
    let read = 0;
    const cancel = vi.fn();
    const stream = new ReadableStream({
      pull(controller) {
        read++;
        controller.enqueue(new Uint8Array(read === 1 ? 8000 : 9000));
      },
      cancel,
    });
    const req = new Request(`${base}/api/agent/source-connections/canvas/pairing`, {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json", "Content-Length": "1" },
      body: stream,
      duplex: "half",
    } as RequestInit);
    const result = await forward(req, [...paths[0][1]], deps);
    expect(result.status).toBe(413);
    expect(cancel).toHaveBeenCalled();
    expect(read).toBeLessThanOrEqual(3); // Stream may prefetch one chunk.
    expect(deps.fetch).not.toHaveBeenCalled();
    expect(result.headers.get("cache-control")).toBe("no-store");
  });

  it("accepts exactly16KiB and forwards body without interpretation", async () => {
    const deps = dependencies();
    const body = JSON.stringify({ origin: "x".repeat(16371) });
    expect(new TextEncoder().encode(body).length).toBe(16384);
    expect(
      (await forward(request(paths[0][1], "POST", base, body), [...paths[0][1]], deps)).status,
    ).toBe(200);
    expect(deps.fetch.mock.calls[0][1]?.body).toBe(body);
  });

  it("rejects malformed UTF-8 without forwarding or reflecting input", async () => {
    const deps = dependencies();
    const req = new Request(`${base}/api/agent/source-connections/canvas/pairing`, {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json" },
      body: new Uint8Array([255, 80, 82, 73, 86, 65, 84, 69]),
    });
    const result = await forward(req, [...paths[0][1]], deps);
    expect(result.status).toBe(422);
    expect(await result.text()).not.toContain("PRIVATE");
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it.each([400, 401, 404, 422, 429, 503])(
    "preserves controlled backend status %i",
    async (status) => {
      const deps = dependencies();
      deps.fetch.mockResolvedValue(Response.json({ detail: "Controlled" }, { status }));
      const result = await forward(request(paths[0][1]), [...paths[0][1]], deps);
      expect(result.status).toBe(status);
      expect(result.headers.get("cache-control")).toBe("no-store");
    },
  );

  it("keeps transport errors secret-free", async () => {
    const deps = dependencies();
    deps.fetch.mockRejectedValue(new Error("PRIVATE_TOKEN"));
    const result = await forward(request(paths[0][1]), [...paths[0][1]], deps);
    expect(result.status).toBe(503);
    expect(await result.text()).not.toContain("PRIVATE");
    expect(deps.fetch).toHaveBeenCalledTimes(1);
  });

  it("requires an unexpired server token even with a browser bearer", async () => {
    const deps = dependencies();
    deps.session.mockResolvedValue({ userId: "alice", getToken: async () => "" });
    const result = await forward(request(paths[0][1]), [...paths[0][1]], deps);
    expect(result.status).toBe(401);
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("refuses Canvas body handling before origin and session checks", async () => {
    const deps = dependencies();
    const req = request(paths[0][1], "POST", "https://wrong.example");
    const read = vi.spyOn(req.body!, "getReader");
    expect((await forward(req, [...paths[0][1]], deps)).status).toBe(403);
    expect(read).not.toHaveBeenCalled();
  });

  it("keeps body stream errors controlled and does not forward partial content", async () => {
    const deps = dependencies();
    const body = new ReadableStream({
      start(c) {
        c.error(new Error("PRIVATE_STREAM"));
      },
    });
    const req = new Request(`${base}/api/agent/source-connections/canvas/pairing`, {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json" },
      body,
      duplex: "half",
    } as RequestInit);
    const result = await forward(req, [...paths[0][1]], deps);
    expect(result.status).toBe(503);
    expect(await result.text()).not.toContain("PRIVATE");
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("preserves overflow413 when cancellation also fails", async () => {
    const deps = dependencies();
    const body = new ReadableStream({
      start(c) {
        c.enqueue(new Uint8Array(16385));
      },
      cancel() {
        throw new Error("PRIVATE_CANCEL");
      },
    });
    const req = new Request(`${base}/api/agent/source-connections/canvas/pairing`, {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json" },
      body,
      duplex: "half",
    } as RequestInit);
    const result = await forward(req, [...paths[0][1]], deps);
    expect(result.status).toBe(413);
    expect(await result.text()).not.toContain("PRIVATE");
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("forwards an empty revoke body while retaining verified session authority", async () => {
    const deps = dependencies();
    expect(
      (await forward(request(paths[2][1], "POST", base, ""), [...paths[2][1]], deps)).status,
    ).toBe(200);
    expect(deps.fetch.mock.calls[0][1]?.body).toBe("");
  });

  it("requires JSON and forwards no request on unsupported content type", async () => {
    const deps = dependencies();
    const req = request(paths[0][1]);
    req.headers.set("content-type", "text/plain");
    expect((await forward(req, [...paths[0][1]], deps)).status).toBe(415);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
});
