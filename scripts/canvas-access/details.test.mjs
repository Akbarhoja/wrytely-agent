import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";
import {
  CDN_ORIGIN,
  FILE_ORIGIN,
  makeFileTransport,
  MAX_PDF_BYTES,
  probeDetails,
  readPdf,
  resolvePdfMetadata,
  validateScope,
} from "./details.mjs";

const origin = "https://canvas.example.edu";
const pdf = new TextEncoder().encode("%PDF-1.7\nPRIVATE_SYLLABUS\n%%EOF");
const hash = async (bytes) =>
  [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
const sample = {
  courseId: "101",
  fileId: "31",
  expectedSha256: await hash(pdf),
};
const config = { origin, courseIds: ["101"], fileSamples: [sample] };
const json = (data) =>
  new Response(JSON.stringify(data), {
    headers: { "content-type": "application/json" },
  });
const metadata = {
  id: 31,
  url: FILE_ORIGIN + "/files/private/sample.pdf?token=PRIVATE_TOKEN",
};
const responsePdf = () =>
  new Response(pdf, { headers: { "content-type": "application/pdf" } });

function provider({ switchOnFile = false, noRubric = false } = {}) {
  let switched = false;
  return async (url, options) => {
    const u = new URL(url);
    assert.equal(options.method, "GET");
    assert.equal(
      options.redirect,
      u.origin === FILE_ORIGIN ? "manual" : "error",
    );
    if (u.origin === FILE_ORIGIN) {
      assert.equal(options.credentials, "omit");
      if (switchOnFile) switched = true;
      return responsePdf();
    }
    assert.equal(u.origin, origin);
    assert.equal(options.credentials, "include");
    if (u.pathname.endsWith("/profile"))
      return json({ id: switched ? 98 : 99 });
    if (u.pathname === "/api/v1/courses") return json([{ id: 101 }]);
    if (u.pathname.endsWith("/files/31")) return json(metadata);
    if (u.pathname.endsWith("/assignments/11"))
      return json({
        id: 11,
        rubric: noRubric
          ? []
          : [{ description: "PRIVATE_CRITERION", points: 5 }],
      });
    if (u.pathname.endsWith("/assignments"))
      return json([
        { id: 11, description: "PRIVATE_ASSIGNMENT", rubric_settings: {} },
      ]);
    if (u.pathname.endsWith("/discussion_topics")) return json([]);
    return json({ syllabus_body: "PRIVATE_SYLLABUS" });
  };
}

test("reads exact PDF bytes and bounded rubric detail without leaking content or URLs", async () => {
  const report = await probeDetails(config, provider());
  const resources = report.courses[0].resources;
  assert.equal(resources.linkedPdf.byteLength, pdf.length);
  assert.equal(resources.linkedPdf.matchesOperatorSample, true);
  assert.equal(resources.rubricDetails.withRubric, 1);
  assert.equal(resources.rubricDetails.criteria, 1);
  assert.equal(report.diagnosticVersion, 5);
  assert.ok(!JSON.stringify(report).includes("PRIVATE"));
  assert.ok(!JSON.stringify(report).includes(FILE_ORIGIN));
});

test("no rubric in sample stays explicitly unproved", async () => {
  const report = await probeDetails(config, provider({ noRubric: true }));
  assert.equal(
    report.courses[0].resources.rubricDetails.coverage,
    "no_rubric_observed_in_sample",
  );
});

test("account switch during file read discards the entire report", async () => {
  await assert.rejects(
    probeDetails(config, provider({ switchOnFile: true })),
    /account_switched_discarded/,
  );
});

for (const bad of [
  { ...config, courseIds: ["101", "101"] },
  { ...config, courseIds: ["101", "102", "103"] },
  { ...config, courseIds: [101] },
  { ...config, fileSamples: [{ ...sample, courseId: "102" }] },
  { ...config, fileSamples: [{ ...sample, fileId: "../31" }] },
  { ...config, fileSamples: [{ ...sample, expectedSha256: "bad" }] },
  { ...config, fileSamples: [sample, sample] },
])
  test(
    "scope rejects before any provider request: " +
      JSON.stringify(bad.courseIds) +
      "/" +
      JSON.stringify(bad.fileSamples),
    async () => {
      assert.throws(() => validateScope(bad), /invalid_detail_scope/);
      let calls = 0;
      await assert.rejects(
        probeDetails(bad, () => {
          calls++;
        }),
        /invalid_detail_scope/,
      );
      assert.equal(calls, 0);
    },
  );

for (const url of [
  "http://inst-fs-iad-prod.inscloudgate.net/files/x",
  "https://evil.example/files/x",
  FILE_ORIGIN + "/other/x",
  FILE_ORIGIN + "/files/x#fragment",
  "https://u:p@inst-fs-iad-prod.inscloudgate.net/files/x",
])
  test("reject unsafe file origin/path before fetch: " + url, async () => {
    let calls = 0;
    await assert.rejects(
      readPdf({ ...metadata, url }, sample, () => {
        calls++;
      }),
      /unsafe_file_url/,
    );
    assert.equal(calls, 0);
  });

for (const change of [
  { id: 32 },
  { locked_for_user: true },
  { hidden_for_user: true },
])
  test(
    "file identity/access fails closed: " + JSON.stringify(change),
    async () => {
      await assert.rejects(
        readPdf({ ...metadata, ...change }, sample, () => assert.fail()),
        /file_scope_or_access_denied/,
      );
    },
  );

test("network failure is controlled and does not expose the signed URL", async () => {
  await assert.rejects(
    readPdf(metadata, sample, () => {
      throw Error("PRIVATE_URL");
    }),
    /file_network_failed/,
  );
});

test("MIME, advertised size, streamed size and signature reject", async () => {
  for (const [response, reason] of [
    [new Response(pdf), "file_not_pdf"],
    [
      new Response(pdf, {
        headers: {
          "content-type": "application/pdf",
          "content-length": MAX_PDF_BYTES + 1,
        },
      }),
      "file_size_limit",
    ],
    [
      new Response(new Uint8Array(MAX_PDF_BYTES + 1), {
        headers: { "content-type": "application/pdf" },
      }),
      "file_size_limit",
    ],
    [
      new Response("<html>PRIVATE</html>", {
        headers: { "content-type": "application/pdf" },
      }),
      "file_invalid_signature",
    ],
  ])
    await assert.rejects(
      readPdf(metadata, sample, () => response),
      new RegExp(reason),
    );
});

test("different bytes are not certified as the locally extracted sample", async () => {
  const result = await readPdf(
    metadata,
    { ...sample, expectedSha256: "0".repeat(64) },
    responsePdf,
  );
  assert.equal(result.matchesOperatorSample, false);
  assert.equal(result.textExtraction, "separate_local_sample_only");
});

test("same-origin exact download wrapper resolves via fixed Canvas API before storage fetch", async () => {
  const calls = [];
  const base = provider();
  const fetch = async (url, options) => {
    calls.push(new URL(url).pathname);
    if (new URL(url).pathname.endsWith("/files/31"))
      return json({
        ...metadata,
        url: origin + "/files/31/download?download_frd=1",
      });
    if (new URL(url).pathname === "/api/v1/files/31/public_url")
      return json({ public_url: metadata.url });
    return base(url, options);
  };
  const result = await probeDetails(config, fetch);
  assert.equal(
    result.courses[0].resources.linkedPdf.matchesOperatorSample,
    true,
  );
  assert.equal(
    calls.filter((p) => p === "/api/v1/files/31/public_url").length,
    1,
  );
  assert.ok(!calls.includes("/files/31/download"));
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
});

for (const path of [
  "/files/32/download",
  "/files/31/download?token=private",
  "/files/31/download?download_frd=2",
  "/files/31/download?download_frd=1&download_frd=1",
  "/courses/101/files/31",
  "/files/31/download#fragment",
])
  test(
    "reject unexpected first-party wrapper without resolver request: " + path,
    async () => {
      let calls = 0;
      await assert.rejects(
        resolvePdfMetadata(
          {
            get: () => {
              calls++;
            },
          },
          { ...metadata, url: origin + path },
          sample,
          origin,
        ),
        /unsafe_file_url/,
      );
      assert.equal(calls, 0);
    },
  );

test("resolver output cannot authorize another storage host", async () => {
  const resolved = await resolvePdfMetadata(
    {
      get: async () => ({
        data: { public_url: "https://evil.example/files/private" },
      }),
    },
    { ...metadata, url: origin + "/files/31/download" },
    sample,
    origin,
  );
  await assert.rejects(
    readPdf(resolved, sample, () => assert.fail()),
    /unsafe_file_url/,
  );
});

test("locked metadata cannot request a preview link", async () => {
  let calls = 0;
  await assert.rejects(
    resolvePdfMetadata(
      {
        get: () => {
          calls++;
        },
      },
      {
        ...metadata,
        locked_for_user: true,
        url: origin + "/files/31/download",
      },
      sample,
      origin,
    ),
    /file_scope_or_access_denied/,
  );
  assert.equal(calls, 0);
});

test("account switch during preview resolution prevents the PDF fetch", async () => {
  const base = provider();
  let switched = false,
    fileReads = 0;
  await assert.rejects(
    probeDetails(config, async (url, options) => {
      const u = new URL(url);
      if (u.origin === FILE_ORIGIN) {
        fileReads++;
        return responsePdf();
      }
      if (u.pathname.endsWith("/profile") && switched) return json({ id: 98 });
      if (u.pathname.endsWith("/files/31"))
        return json({ ...metadata, url: origin + "/files/31/download" });
      if (u.pathname === "/api/v1/files/31/public_url") {
        switched = true;
        return json({ public_url: metadata.url });
      }
      return base(url, options);
    }),
    /account_switched_discarded/,
  );
  assert.equal(fileReads, 0);
});

test("restricted detail resource is reported without provider error text", async () => {
  const fetch = provider();
  const report = await probeDetails(config, (url, options) =>
    new URL(url).pathname.endsWith("/assignments/11")
      ? new Response("PRIVATE_ERROR", { status: 403 })
      : fetch(url, options),
  );
  assert.deepEqual(report.courses[0].resources.rubricDetails, {
    state: "incomplete",
    reason: "permission_denied",
  });
  assert.ok(!JSON.stringify(report).includes("PRIVATE"));
});

test("prepared extension has exact permissions and accepts only its own popup", async () => {
  const directory = await mkdtemp(join(tmpdir(), "wrytely-diagnostic-test-"));
  const priorChrome = globalThis.chrome,
    priorFetch = globalThis.fetch;
  try {
    const source = join(directory, "scope.json"),
      output = join(directory, "unpacked");
    await writeFile(source, JSON.stringify(config));
    execFileSync(process.execPath, [
      new URL("prepare.mjs", import.meta.url).pathname,
      source,
      output,
    ]);
    const manifest = JSON.parse(
      await readFile(join(output, "manifest.json"), "utf8"),
    );
    assert.deepEqual(manifest.host_permissions, [
      origin + "/*",
      FILE_ORIGIN + "/*",
      CDN_ORIGIN + "/*",
    ]);
    assert.equal(manifest.version, "0.0.5");
    assert.deepEqual(manifest.permissions, ["webRequest"]);
    assert.equal(manifest.action.default_popup, "popup.html");
    let listener;
    const badges = [];
    globalThis.chrome = {
      runtime: {
        id: "synthetic",
        getURL: (x) => "chrome-extension://synthetic/" + x,
        onMessage: {
          addListener: (value) => {
            listener = value;
          },
        },
      },
      permissions: {
        contains: async (value) => {
          assert.ok(
            [FILE_ORIGIN, CDN_ORIGIN].some(
              (host) =>
                JSON.stringify(value) ===
                JSON.stringify({ origins: [`${host}/*`] }),
            ),
          );
          return true;
        },
      },
      webRequest: {
        onHeadersReceived: { addListener: () => {}, removeListener: () => {} },
      },
      action: {
        setBadgeText: async (value) => {
          badges.push(value.text);
        },
      },
    };
    globalThis.fetch = provider();
    await import(pathToFileURL(join(output, "worker.mjs")).href);
    assert.equal(
      listener(
        { kind: "run" },
        { id: "attacker", url: "https://evil.example" },
        () => assert.fail(),
      ),
      undefined,
    );
    assert.deepEqual(badges, []);
    const result = await new Promise((resolve) => {
      assert.equal(
        listener(
          { kind: "run" },
          { id: "synthetic", url: "chrome-extension://synthetic/popup.html" },
          resolve,
        ),
        true,
      );
    });
    assert.equal(result.diagnosticVersion, 5);
    assert.equal(result.fileHostPermissionGranted, true);
    assert.deepEqual(badges, ["RUN", "READ"]);
    assert.ok(!JSON.stringify(result).includes("PRIVATE"));
  } finally {
    globalThis.chrome = priorChrome;
    globalThis.fetch = priorFetch;
    await rm(directory, { recursive: true, force: true });
  }
});

for (const redirect of [
  { type: "opaqueredirect", status: 0, ok: false },
  { type: "basic", status: 302, ok: false },
]) {
  test(`reports redirect without reading destination: ${redirect.type}`, async () => {
    let cancelled = false;
    await assert.rejects(
      readPdf(metadata, sample, async (_url, options) => {
        assert.equal(options.redirect, "manual");
        assert.equal(options.credentials, "omit");
        return {
          ...redirect,
          body: {
            cancel: async () => {
              cancelled = true;
            },
          },
        };
      }),
      /file_redirect_blocked/,
    );
    assert.equal(cancelled, true);
  });
}

const cdnUrl =
  CDN_ORIGIN +
  "/11111111-1111-1111-1111-111111111111/sample.pdf?token=PRIVATE_CDN&content_type=application%2Fpdf";
const opaqueRedirect = () => ({
  type: "opaqueredirect",
  status: 0,
  ok: false,
  body: null,
});

test("manually follows one exact CDN hop with identity check and no credential forwarding", async () => {
  const calls = [];
  let identityChecked = false;
  const result = await readPdf(
    metadata,
    sample,
    async (url, options) => {
      calls.push(url);
      assert.equal(options.redirect, "manual");
      assert.equal(options.credentials, "omit");
      if (calls.length === 1) return opaqueRedirect();
      assert.equal(identityChecked, true);
      assert.equal(url, cdnUrl);
      return responsePdf();
    },
    () => cdnUrl,
    async () => {
      identityChecked = true;
    },
  );
  assert.equal(calls.length, 2);
  assert.equal(result.redirectsFollowed, 1);
  assert.equal(result.matchesOperatorSample, true);
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
});

for (const bad of [
  cdnUrl.replace("https:", "http:"),
  cdnUrl.replace("cdn.inst-fs-iad-prod.inscloudgate.net", "evil.example"),
  cdnUrl.replace(".net/", ".net.evil.example/"),
  cdnUrl.replace("https://", "https://user:pass@"),
  cdnUrl + "#fragment",
  cdnUrl + "&other=value",
  cdnUrl + "&token=duplicate",
  cdnUrl.replace("sample.pdf", "sample.html"),
  cdnUrl.replace("application%2Fpdf", "text%2Fhtml"),
  cdnUrl.replace("11111111-1111-1111-1111-111111111111/", "other/"),
]) {
  test(
    "rejects unexpected CDN destination before fetching: " +
      bad.replace(/token=[^&]*/, "token=REDACTED"),
    async () => {
      let calls = 0;
      await assert.rejects(
        readPdf(
          metadata,
          sample,
          async () => {
            calls++;
            return opaqueRedirect();
          },
          () => bad,
        ),
        /unsafe_file_redirect/,
      );
      assert.equal(calls, 1);
    },
  );
}

test("a second redirect never triggers a third request", async () => {
  let calls = 0;
  await assert.rejects(
    readPdf(
      metadata,
      sample,
      async () => {
        calls++;
        return opaqueRedirect();
      },
      () => cdnUrl,
    ),
    /file_redirect_limit/,
  );
  assert.equal(calls, 2);
});

test("account change before CDN request prevents that request", async () => {
  let calls = 0;
  await assert.rejects(
    readPdf(
      metadata,
      sample,
      async () => {
        calls++;
        return opaqueRedirect();
      },
      () => cdnUrl,
      async () => {
        throw Error("account_switched_discarded");
      },
    ),
    /account_switched_discarded/,
  );
  assert.equal(calls, 1);
});

function observedRequest() {
  let handler;
  const origin = "chrome-extension://synthetic";
  return {
    origin,
    get handler() {
      return handler;
    },
    api: {
      onHeadersReceived: {
        addListener: (listener, filter, extra) => {
          assert.deepEqual(filter, {
            urls: [`${FILE_ORIGIN}/files/*`],
            types: ["xmlhttprequest"],
          });
          assert.deepEqual(extra, ["responseHeaders"]);
          handler = listener;
        },
        removeListener: (listener) => {
          assert.equal(listener, handler);
          handler = null;
        },
      },
    },
  };
}

test("header observer ignores unrelated URLs/initiators/methods and cleans up", async () => {
  const mock = observedRequest();
  const event = {
    url: metadata.url,
    initiator: mock.origin,
    method: "GET",
    statusCode: 302,
    responseHeaders: [{ name: "Location", value: cdnUrl }],
  };
  const response = opaqueRedirect();
  const transport = makeFileTransport(mock.api, mock.origin, async () => {
    mock.handler({
      ...event,
      url: "https://evil.example",
      responseHeaders: [{ name: "Location", value: "https://evil.example" }],
    });
    mock.handler({
      ...event,
      initiator: "https://canvas.example.edu",
      responseHeaders: [{ name: "Location", value: "https://evil.example" }],
    });
    mock.handler({
      ...event,
      method: "POST",
      responseHeaders: [{ name: "Location", value: "https://evil.example" }],
    });
    mock.handler(event);
    return response;
  });
  assert.equal(await transport.fetch(metadata.url, {}), response);
  assert.equal(transport.location(response), cdnUrl);
  assert.equal(mock.handler, null);
  assert.equal(transport.location(opaqueRedirect()), null);
});

test("observer handles delayed header dispatch without leaking listener", async () => {
  const mock = observedRequest();
  const response = opaqueRedirect();
  const transport = makeFileTransport(mock.api, mock.origin, async () => {
    setTimeout(
      () =>
        mock.handler({
          url: metadata.url,
          initiator: mock.origin,
          method: "GET",
          statusCode: 302,
          responseHeaders: [{ name: "location", value: cdnUrl }],
        }),
      0,
    );
    return response;
  });
  await transport.fetch(metadata.url, {});
  assert.equal(transport.location(response), cdnUrl);
  assert.equal(mock.handler, null);
});

test("duplicate Location headers do not provide a destination", async () => {
  const mock = observedRequest();
  const response = opaqueRedirect();
  const transport = makeFileTransport(mock.api, mock.origin, async () => {
    mock.handler({
      url: metadata.url,
      initiator: mock.origin,
      method: "GET",
      statusCode: 302,
      responseHeaders: [
        { name: "Location", value: cdnUrl },
        { name: "Location", value: cdnUrl },
      ],
    });
    return response;
  });
  await transport.fetch(metadata.url, {});
  assert.equal(transport.location(response), null);
  assert.equal(mock.handler, null);
});

test("observer cleanup happens on thrown fetch and nonredirect responses", async () => {
  const mock = observedRequest();
  const transport = makeFileTransport(mock.api, mock.origin, async () => {
    throw Error("synthetic");
  });
  await assert.rejects(transport.fetch(metadata.url, {}), /synthetic/);
  assert.equal(mock.handler, null);
  const success = makeFileTransport(mock.api, mock.origin, async () =>
    responsePdf(),
  );
  await success.fetch(metadata.url, {});
  assert.equal(mock.handler, null);
});
