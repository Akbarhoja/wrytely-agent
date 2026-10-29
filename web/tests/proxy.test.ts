// @vitest-environment node
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { NextFetchEvent, NextRequest } from "next/server";
import config from "../next.config";

let proxy: typeof import("../proxy").default;
let RequestType: typeof import("next/server").NextRequest;
const noProviderFetch = vi.fn(async () => {
  throw new Error("Provider IO is disabled in this synthetic fixture");
});

beforeAll(async () => {
  // Synthetic test-format configuration: no real issuer, session or credential.
  vi.stubEnv(
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "pk_test_" + Buffer.from("clerk.offline.invalid$").toString("base64"),
  );
  vi.stubEnv("CLERK_SECRET_KEY", "sk_test_offline_synthetic_fixture");
  vi.stubEnv("NEXT_PUBLIC_CLERK_KEYLESS_DISABLED", "true");
  vi.stubEnv("NEXT_PUBLIC_CLERK_TELEMETRY_DISABLED", "true");
  // Next derives this request-constructor setting from next.config at build time.
  vi.stubEnv("__NEXT_NO_MIDDLEWARE_URL_NORMALIZE", config.skipProxyUrlNormalize ? "1" : "");
  vi.stubGlobal("fetch", noProviderFetch);
  RequestType = (await import("next/server")).NextRequest;
  proxy = (await import("../proxy")).default;
});

afterAll(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("configured Clerk proxy origin boundary", () => {
  it("retains Clerk's normal signed-out browser handshake without provider IO", async () => {
    const request = new RequestType("http://127.0.0.1:3000/sign-in", {
      headers: { accept: "text/html" },
    });
    const response = await proxy(
      request as NextRequest,
      { waitUntil() {} } as unknown as NextFetchEvent,
    );
    expect(response?.status).toBe(307);
    expect(noProviderFetch).not.toHaveBeenCalled();
  });
  it.each(["/", "/sign-in", "/api/agent/me", "/?probe=one"])(
    "keeps the internal signed-out rewrite on the actual origin for %s",
    async (path) => {
      const url = "http://127.0.0.1:3000" + path;
      const request = new RequestType(url, { headers: { accept: "application/json" } });
      const response = await proxy(
        request as NextRequest,
        { waitUntil() {} } as unknown as NextFetchEvent,
      );
      expect(response?.headers.get("x-middleware-rewrite")).toBe(url);
      expect(response?.headers.get("x-middleware-request-x-clerk-auth-status")).toBe("signed-out");
      expect(noProviderFetch).not.toHaveBeenCalled();
    },
  );
});
