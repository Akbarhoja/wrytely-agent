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

describe("private connection list proxy", () => {
  function listRequest(query = "") {
    return new Request(`${base}/api/agent/source-connections${query}`, {
      headers: {
        Authorization: "Bearer browser",
        Cookie: "PRIVATE_COOKIE",
        "X-User-Id": "bob",
      },
    });
  }

  it.each(["", "?limit=1", "?limit=20", "?limit=01", `?limit=2&cursor=${uuid}`])(
    "forwards bounded list pagination %s with verified authority",
    async (query) => {
      const deps = dependencies();
      const page = { connections: [], next_cursor: query ? uuid : null };
      deps.fetch.mockResolvedValue(Response.json(page));
      const result = await forward(listRequest(query), ["source-connections"], deps);
      expect(result.status).toBe(200);
      expect(await result.json()).toEqual(page);
      expect(result.headers.get("cache-control")).toBe("no-store");
      expect(deps.fetch).toHaveBeenCalledTimes(1);
      const [url, init] = deps.fetch.mock.calls[0];
      expect(url).toBe(`https://backend.example/v1/source-connections${query}`);
      const headers = new Headers(init?.headers);
      expect(headers.get("authorization")).toBe("Bearer verified");
      expect(headers.get("cookie")).toBeNull();
      expect(headers.get("x-user-id")).toBeNull();
      expect(headers.get("idempotency-key")).toBeNull();
      expect(init?.body).toBeUndefined();
      expect(init?.method).toBe("GET");
      expect(init?.cache).toBe("no-store");
      expect(init?.redirect).toBe("error");
      expect(init?.signal).toBeDefined();
    },
  );

  it.each([
    "?limit=0",
    "?limit=21",
    "?limit=-1",
    "?limit=1.5",
    "?limit=",
    "?limit=001",
    "?limit=%2B1",
    "?limit=%EF%BC%91",
    "?limit=1&limit=2",
    "?limit=1&%6cimit=2",
    "?cursor=a&cursor=b",
    "?user_id=PRIVATE",
    "?limit=1&unknown=PRIVATE",
    `?cursor=${"x".repeat(129)}`,
    `?cursor=${"%41".repeat(342)}`,
  ])("rejects invalid pagination without reflecting or forwarding %s", async (query) => {
    const deps = dependencies();
    const result = await forward(listRequest(query), ["source-connections"], deps);
    expect(result.status).toBe(422);
    expect(await result.json()).toEqual({ detail: "Invalid Canvas request." });
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it.each(["", "?cursor=", "?cursor=not-a-uuid", "?cursor=urn%3Auuid%3A" + uuid])(
    "preserves backend private cursor rejection for %s",
    async (query) => {
      const deps = dependencies();
      deps.fetch.mockResolvedValue(Response.json({ detail: "Not found" }, { status: 404 }));
      const result = await forward(listRequest(query), ["source-connections"], deps);
      expect(result.status).toBe(404);
      expect(result.headers.get("cache-control")).toBe("no-store");
      expect(deps.fetch).toHaveBeenCalledTimes(1);
    },
  );

  it("re-encodes opaque cursor text instead of admitting query or path injection", async () => {
    const deps = dependencies();
    const cursor = "a&user_id=bob#../private?limit=20";
    const result = await forward(
      listRequest(`?cursor=${encodeURIComponent(cursor)}`),
      ["source-connections"],
      deps,
    );
    expect(result.status).toBe(200);
    const url = new URL(String(deps.fetch.mock.calls[0][0]));
    expect(url.pathname).toBe("/v1/source-connections");
    expect([...url.searchParams]).toEqual([["cursor", cursor]]);
    expect(url.hash).toBe("");
  });

  it("accepts the exact cursor and raw-query ceilings, rejecting the next query unit", async () => {
    for (const cursor of ["x".repeat(128), "€".repeat(112) + "x".repeat(8)]) {
      const deps = dependencies();
      const query = `?cursor=${encodeURIComponent(cursor)}`;
      expect((await forward(listRequest(query), ["source-connections"], deps)).status).toBe(200);
      expect(new URL(String(deps.fetch.mock.calls[0][0])).searchParams.get("cursor")).toBe(cursor);
    }
    const deps = dependencies();
    const over = `?cursor=${encodeURIComponent("€".repeat(112) + "x".repeat(9))}`;
    expect(over.length).toBe(1025);
    expect((await forward(listRequest(over), ["source-connections"], deps)).status).toBe(422);
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("preserves the list projection and follows a returned cursor into the next page", async () => {
    const deps = dependencies();
    const connection = {
      connection_id: uuid,
      provider: "canvas",
      origin: "https://canvas.example",
      state: "connected",
      generation: 1,
      credential_expires_at: "2026-11-01T00:00:00Z",
    };
    deps.fetch.mockResolvedValueOnce(
      Response.json({ connections: [connection], next_cursor: uuid }),
    );
    deps.fetch.mockResolvedValueOnce(Response.json({ connections: [], next_cursor: null }));
    const first = await (
      await forward(listRequest("?limit=1"), ["source-connections"], deps)
    ).json();
    expect(first.connections).toEqual([connection]);
    const next = await forward(
      listRequest(`?limit=1&cursor=${first.next_cursor}`),
      ["source-connections"],
      deps,
    );
    expect(await next.json()).toEqual({ connections: [], next_cursor: null });
    expect(deps.fetch.mock.calls[1][0]).toBe(
      `https://backend.example/v1/source-connections?limit=1&cursor=${uuid}`,
    );
  });

  it("returns private503 without an upstream configuration", async () => {
    const deps = dependencies();
    deps.configured = false;
    const result = await forward(listRequest(), ["source-connections"], deps);
    expect(result.status).toBe(503);
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(deps.session).not.toHaveBeenCalled();
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it.each(["signed-out", "expired"])("requires verified auth: %s", async (state) => {
    const deps = dependencies();
    deps.session.mockResolvedValue({
      userId: state === "signed-out" ? "" : "alice",
      getToken: async () => "",
    });
    const result = await forward(listRequest("?user_id=PRIVATE"), ["source-connections"], deps);
    expect(result.status).toBe(401);
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(deps.fetch).not.toHaveBeenCalled();
  });

  it("uses each request's server session without retaining another account token", async () => {
    const deps = dependencies();
    for (const user of ["alice", "bob"]) {
      deps.session.mockResolvedValue({ userId: user, getToken: async () => `${user}-verified` });
      expect((await forward(listRequest(), ["source-connections"], deps)).status).toBe(200);
    }
    expect(
      deps.fetch.mock.calls.map(([, init]) => new Headers(init?.headers).get("authorization")),
    ).toEqual(["Bearer alice-verified", "Bearer bob-verified"]);
  });

  it.each([401, 404, 422, 429, 503])(
    "preserves controlled error %i without retry",
    async (status) => {
      const deps = dependencies();
      deps.fetch.mockResolvedValue(Response.json({ detail: "Controlled" }, { status }));
      const result = await forward(listRequest(), ["source-connections"], deps);
      expect(result.status).toBe(status);
      expect(result.headers.get("cache-control")).toBe("no-store");
      expect(deps.fetch).toHaveBeenCalledTimes(1);
    },
  );

  it("redacts transport errors and makes one attempt", async () => {
    const deps = dependencies();
    deps.fetch.mockRejectedValue(new Error("PRIVATE_TOKEN"));
    const result = await forward(listRequest(), ["source-connections"], deps);
    expect(result.status).toBe(503);
    expect(await result.text()).not.toContain("PRIVATE");
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(deps.fetch).toHaveBeenCalledTimes(1);
  });

  it.each([["source-connections", ""], ["source-connections/"], ["source-connections", ".."]])(
    "rejects disguised list path %j",
    async (...path) => {
      const deps = dependencies();
      expect((await forward(listRequest(), path, deps)).status).toBe(404);
      expect(deps.session).not.toHaveBeenCalled();
      expect(deps.fetch).not.toHaveBeenCalled();
    },
  );

  it("keeps list POST unavailable", async () => {
    const deps = dependencies();
    expect(
      (await forward(request(["source-connections"]), ["source-connections"], deps)).status,
    ).toBe(404);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
});
