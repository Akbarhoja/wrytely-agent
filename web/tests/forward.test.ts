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
  it.each([
    "v2/responsibilities/00000000-0000-4000-8000-000000000001/artifacts?limit=1&before=opaque_cursor",
    "v2/artifacts/00000000-0000-4000-8000-000000000001",
    "v2/artifacts/00000000-0000-4000-8000-000000000001/evidence/policy/0?check_id=00000000-0000-4000-8000-000000000002",
  ])("forwards exact versioned private result %s with verified identity", async (input) => {
    const deps = dependencies();
    const path = input.split("?")[0].split("/");
    const response = await forward(request(input, "GET"), path, deps);
    expect(response.status).toBe(202);
    expect(deps.fetch.mock.calls[0][0]).toBe(`http://agent.internal:8000/${input}`);
    const headers = new Headers(deps.fetch.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer verified-session-token");
    expect(headers.has("Cookie")).toBe(false);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect((await forward(request(input), path, deps)).status).toBe(404);
  });
  it.each([
    "v2/artifacts/00000000-0000-4000-8000-000000000001?user_id=other",
    "v2/responsibilities/00000000-0000-4000-8000-000000000001/artifacts?limit=1&limit=2",
    "v2/artifacts/00000000-0000-4000-8000-000000000001/evidence/citation/0?source_id=other",
  ])("rejects unexpected private-result query %s before forwarding", async (input) => {
    const deps = dependencies();
    const response = await forward(request(input, "GET"), input.split("?")[0].split("/"), deps);
    expect(response.status).toBe(400);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it("permits only authenticated same-origin explicit delegation and private status reads", async () => {
    const deps = dependencies();
    expect((await forward(request("responsibilities"), ["responsibilities"], deps)).status).toBe(
      202,
    );
    expect(new Headers(deps.fetch.mock.calls[0][1]?.headers).get("Authorization")).toBe(
      "Bearer verified-session-token",
    );
    expect(new Headers(deps.fetch.mock.calls[0][1]?.headers).get("Idempotency-Key")).toBe(
      "stable-key",
    );
    const path = "responsibilities/00000000-0000-4000-8000-000000000001/status";
    expect((await forward(request(path, "GET"), path.split("/"), deps)).status).toBe(202);
    deps.fetch.mockClear();
    expect(
      (
        await forward(
          request("responsibilities", "POST", "https://evil.example"),
          ["responsibilities"],
          deps,
        )
      ).status,
    ).toBe(403);
    expect((await forward(request(path), path.split("/"), deps)).status).toBe(404);
    expect(
      (
        await forward(
          request("responsibilities/bad/status", "GET"),
          ["responsibilities", "bad", "status"],
          deps,
        )
      ).status,
    ).toBe(404);
    expect(deps.fetch).not.toHaveBeenCalled();
    deps.session.mockResolvedValue({ userId: null as unknown as string, getToken: async () => "" });
    expect((await forward(request("responsibilities"), ["responsibilities"], deps)).status).toBe(
      401,
    );
  });
  it.each([
    "responsibilities",
    "responsibilities/00000000-0000-0000-0000-000000000000/artifacts",
    "artifacts/00000000-0000-0000-0000-000000000000",
  ])(
    "allows verified private result read %s with only the explicit create mutation",
    async (path) => {
      const deps = dependencies();
      const response = await forward(request(path, "GET"), path.split("/"), deps);
      expect(response.status).toBe(202);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(new Headers(deps.fetch.mock.calls[0][1]?.headers).get("Authorization")).toBe(
        "Bearer verified-session-token",
      );
      expect((await forward(request(path), path.split("/"), deps)).status).toBe(
        path === "responsibilities" ? 202 : 404,
      );
      deps.session.mockResolvedValue({
        userId: null as unknown as string,
        getToken: async () => "",
      });
      expect((await forward(request(path, "GET"), path.split("/"), deps)).status).toBe(401);
    },
  );
  it.each([
    "artifacts/all",
    "artifacts/not-a-uuid",
    "responsibilities/not-a-uuid/artifacts",
    "responsibilities/admin",
    "artifacts/00000000-0000-0000-0000-000000000000/approve",
  ])("does not expose arbitrary artifact route %s", async (path) => {
    const deps = dependencies();
    expect((await forward(request(path, "GET"), path.split("/"), deps)).status).toBe(404);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it.each(["sources", "sources/00000000-0000-0000-0000-000000000000"])(
    "forwards private snapshot read %s through verified session only",
    async (path) => {
      const deps = dependencies();
      const response = await forward(request(path, "GET"), path.split("/"), deps);
      expect(response.status).toBe(202);
      expect(deps.fetch.mock.calls[0][0]).toBe(`http://agent.internal:8000/v1/${path}`);
      expect(response.headers.get("cache-control")).toBe("no-store");
      const headers = new Headers(deps.fetch.mock.calls[0][1]?.headers);
      expect(headers.get("Authorization")).toBe("Bearer verified-session-token");
      expect(headers.has("X-User-Id")).toBe(false);
      deps.session.mockResolvedValue({
        userId: null as unknown as string,
        getToken: async () => "",
      });
      expect((await forward(request(path, "GET"), path.split("/"), deps)).status).toBe(401);
    },
  );
  it("allows only same-origin snapshot creation with stable retry identity", async () => {
    const deps = dependencies();
    expect((await forward(request("sources"), ["sources"], deps)).status).toBe(202);
    const headers = new Headers(deps.fetch.mock.calls[0][1]?.headers);
    expect(headers.get("Idempotency-Key")).toBe("stable-key");
    expect(headers.has("Cookie")).toBe(false);
    deps.fetch.mockClear();
    expect(
      (await forward(request("sources", "POST", "https://evil.example"), ["sources"], deps)).status,
    ).toBe(403);
    for (const path of ["sources/not-a-uuid", "sources/admin", "sources/../../me"]) {
      expect((await forward(request(path, "GET"), path.split("/"), deps)).status).toBe(404);
    }
    expect((await forward(request("sources/id"), ["sources", "id"], deps)).status).toBe(404);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it("forwards private WhatsApp reads with only the verified token and no cache", async () => {
    const deps = dependencies();
    const response = await forward(request("whatsapp", "GET"), ["whatsapp"], deps);
    expect(response.status).toBe(202);
    expect(deps.fetch.mock.calls[0][0]).toBe("http://agent.internal:8000/v1/whatsapp");
    expect(response.headers.get("cache-control")).toBe("no-store");
    deps.session.mockResolvedValue({ userId: null as unknown as string, getToken: async () => "" });
    expect((await forward(request("whatsapp", "GET"), ["whatsapp"], deps)).status).toBe(401);
  });
  it.each(["link", "unlink", "preferences"])(
    "allows only the existing WhatsApp %s mutation through the verified session",
    async (action) => {
      const deps = dependencies();
      const path = `whatsapp/${action}`;
      const response = await forward(request(path), ["whatsapp", action], deps);
      expect(response.status).toBe(202);
      expect(deps.fetch.mock.calls[0][0]).toBe(`http://agent.internal:8000/v1/${path}`);
      const options = deps.fetch.mock.calls[0][1];
      expect(new Headers(options?.headers).get("Authorization")).toBe(
        "Bearer verified-session-token",
      );
      expect(options?.cache).toBe("no-store");
      expect(response.headers.get("cache-control")).toBe("no-store");
    },
  );
  it("rejects cross-origin WhatsApp linking and arbitrary WhatsApp routes", async () => {
    const deps = dependencies();
    expect(
      (
        await forward(
          request("whatsapp/link", "POST", "https://evil.example"),
          ["whatsapp", "link"],
          deps,
        )
      ).status,
    ).toBe(403);
    expect((await forward(request("whatsapp/admin"), ["whatsapp", "admin"], deps)).status).toBe(
      404,
    );
    expect(deps.fetch).not.toHaveBeenCalled();
  });
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

describe("session Canvas connection proxy", () => {
  it("forwards bounded coverage queries using the verified session", async () => {
    const deps = dependencies();
    const path = "source-connections/00000000-0000-4000-8000-000000000001/canvas/coverage";
    const response = await forward(
      request(path + "?limit=20&after=101", "GET"),
      path.split("/"),
      deps,
    );
    expect(response.status).toBe(202);
    expect(String(deps.fetch.mock.calls[0][0])).toContain("/v1/" + path + "?limit=20&after=101");
    expect(new Headers(deps.fetch.mock.calls[0][1]?.headers).get("authorization")).toBe(
      "Bearer verified-session-token",
    );
  });
  it.each([
    "source-connections/canvas/redeem",
    "source-connections/canvas/bind",
    "source-connections/canvas/context",
    "source-connections/canvas/documents/file-extract",
  ])("never forwards ingestion operation %s", async (path) => {
    const deps = dependencies();
    expect((await forward(request(path), path.split("/"), deps)).status).toBe(404);
    expect(deps.fetch).not.toHaveBeenCalled();
  });
  it("rejects owner overrides and duplicate queries before fetching", async () => {
    for (const suffix of ["?user_id=bob", "?limit=1&limit=2"]) {
      const deps = dependencies();
      const path = "source-connections";
      expect((await forward(request(path + suffix, "GET"), [path], deps)).status).toBe(400);
      expect(deps.fetch).not.toHaveBeenCalled();
    }
  });
});
