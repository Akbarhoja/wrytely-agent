import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../lib/client";

afterEach(() => vi.unstubAllGlobals());

it.each([
  [401, "<html>PRIVATE upstream session response</html>"],
  [401, "{PRIVATE invalid JSON"],
  [401, "null"],
  [403, "Access denied"],
  [503, "PRIVATE unavailable"],
  [500, "[]"],
])("retains HTTP %s when its error body is not a detail object", async (status, body) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status })),
  );
  let failure: unknown;
  try {
    await api("me");
  } catch (error) {
    failure = error;
  }
  expect(failure).toBeInstanceOf(ApiError);
  expect((failure as ApiError).status).toBe(status);
  expect((failure as Error).message).toBe("Please try again.");
});

it("preserves a valid JSON error detail and status", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ detail: "Expired" }, { status: 401 })),
  );
  await expect(api("me")).rejects.toMatchObject({ status: 401, message: "Expired" });
});

it("returns a valid JSON success with the same private request settings", async () => {
  const fetch = vi.fn(async () => Response.json({ id: "synthetic" }));
  vi.stubGlobal("fetch", fetch);
  await expect(api("me")).resolves.toEqual({ id: "synthetic" });
  expect(fetch).toHaveBeenCalledWith(
    "/api/agent/me",
    expect.objectContaining({
      cache: "no-store",
      credentials: "same-origin",
    }),
  );
});

it("rejects malformed success without including its body in the error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("PRIVATE malformed success")),
  );
  await expect(api("me")).rejects.toThrow("Invalid API response");
});
