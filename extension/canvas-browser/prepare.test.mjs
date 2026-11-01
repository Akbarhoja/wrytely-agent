import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtemp,
  mkdir,
  readFile,
  readdir,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { resolve, dirname, relative, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { prepareCanvasPackage } from "./prepare.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const allowed = resolve(root, ".local/canvas-packages");
async function fixture(t) {
  await mkdir(allowed, { recursive: true });
  const dir = await mkdtemp(resolve(allowed, "test-"));
  t.after(async () => {
    assert.ok(
      relative(allowed, dir) && !relative(allowed, dir).startsWith(".."),
    );
    await rm(dir, { recursive: true, force: true });
  });
  return {
    dir,
    output: resolve(dir, "package"),
    apiOrigin: "https://agent.example.edu",
    canvasOrigin: "https://canvas.example.edu",
  };
}
test("package pins two origins, minimal permissions/CSP and copies only explicit assets", async (t) => {
  const f = await fixture(t);
  await prepareCanvasPackage(f);
  const manifest = JSON.parse(
    await readFile(resolve(f.output, "manifest.json"), "utf8"),
  );
  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.minimum_chrome_version, "120");
  assert.deepEqual(manifest.permissions, ["storage", "alarms"]);
  assert.deepEqual(manifest.host_permissions, [
    f.apiOrigin + "/*",
    f.canvasOrigin + "/*",
  ]);
  assert.deepEqual(manifest.background, {
    service_worker: "worker.mjs",
    type: "module",
  });
  assert.equal(manifest.action.default_popup, "popup.html");
  assert.equal(manifest.options_page, "options.html");
  for (const key of [
    "content_scripts",
    "externally_connectable",
    "web_accessible_resources",
    "optional_host_permissions",
  ])
    assert.equal(key in manifest, false);
  assert.match(
    manifest.content_security_policy.extension_pages,
    /script-src 'self'/,
  );
  assert.match(
    manifest.content_security_policy.extension_pages,
    /object-src 'none'/,
  );
  assert.ok(
    !manifest.content_security_policy.extension_pages.includes("unsafe-"),
  );
  const files = [];
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = resolve(dir, entry.name);
      if (entry.isDirectory()) await walk(path);
      else files.push(relative(f.output, path).split(sep).join("/"));
    }
  }
  await walk(f.output);
  assert.ok(files.includes("canvas-pairing/client.mjs"));
  assert.ok(
    files.every(
      (path) =>
        !path.endsWith(".test.mjs") &&
        !path.includes("http-interop") &&
        !path.endsWith("prepare.mjs"),
    ),
  );
  assert.equal(
    (await readFile(resolve(f.output, "popup.html"), "utf8")).replace(
      'class="popup"',
      'class="surface"',
    ),
    (await readFile(resolve(f.output, "options.html"), "utf8")).replace(
      'class="options"',
      'class="surface"',
    ),
  );
  for (const file of files.filter((x) => x.endsWith(".mjs"))) {
    const source = await readFile(resolve(f.output, file), "utf8");
    for (const match of source.matchAll(/\bfrom\s+["']([^"']+)["']/g)) {
      assert.ok(match[1].startsWith("."));
      const target = resolve(dirname(resolve(f.output, file)), match[1]);
      assert.ok(!relative(f.output, target).startsWith(".."));
      await readFile(target);
    }
  }
  const tokens = await readFile(resolve(f.output, "tokens.css"), "utf8");
  assert.match(tokens, /--green: #24664f/);
  assert.match(tokens, /--bg: #f6f8f7/);
  assert.equal(
    (await readFile(resolve(f.output, "fonts/plus-jakarta-sans-latin.woff2")))
      .subarray(0, 4)
      .toString(),
    "wOF2",
  );
});
test("invalid origins/output cannot create or overwrite files", async (t) => {
  const f = await fixture(t);
  for (const apiOrigin of [
    "http://agent.example.edu",
    "https://agent.example.edu/path",
    "https://user@agent.example.edu",
    "https://agent.example.edu:443",
  ])
    await assert.rejects(prepareCanvasPackage({ ...f, apiOrigin }));
  await assert.rejects(prepareCanvasPackage({ ...f, output: root }));
  await mkdir(f.output);
  await writeFile(resolve(f.output, "sentinel"), "keep");
  await assert.rejects(prepareCanvasPackage(f));
  assert.equal(await readFile(resolve(f.output, "sentinel"), "utf8"), "keep");
});
test("symlinked output ancestors are refused without touching their target", async (t) => {
  const f = await fixture(t);
  const target = resolve(f.dir, "target"),
    link = resolve(f.dir, "link");
  await mkdir(target);
  await symlink(
    target,
    link,
    process.platform === "win32" ? "junction" : "dir",
  );
  await assert.rejects(
    prepareCanvasPackage({ ...f, output: resolve(link, "package") }),
  );
  assert.deepEqual(await readdir(target), []);
});
test("packaged worker starts default-disabled with real host registration and no fetch/alarm creation", async (t) => {
  const f = await fixture(t);
  await prepareCanvasPackage(f);
  const listeners = [],
    data = {};
  let requests = 0,
    created = 0;
  const event = () => ({
    addListener: (fn) => listeners.push(fn),
    removeListener() {},
  });
  const chrome = {
    runtime: {
      id: "synthetic",
      getURL: (p) => `chrome-extension://synthetic/${p}`,
      onMessage: event(),
      onStartup: event(),
      onInstalled: event(),
    },
    storage: {
      local: {
        async setAccessLevel() {},
        async get(key) {
          return { [key]: data[key] };
        },
        async set(value) {
          Object.assign(data, value);
        },
        async remove(key) {
          delete data[key];
        },
      },
    },
    alarms: {
      onAlarm: event(),
      async get() {},
      async create() {
        created++;
      },
      async clear() {
        return false;
      },
    },
  };
  const previousChrome = globalThis.chrome,
    previousFetch = globalThis.fetch;
  globalThis.chrome = chrome;
  globalThis.fetch = async () => {
    requests++;
    throw Error("unexpected IO");
  };
  try {
    await import(pathToFileURL(resolve(f.output, "worker.mjs")));
    await new Promise((r) => setImmediate(r));
    assert.equal(requests, 0);
    assert.equal(created, 0);
    assert.equal(listeners.length, 4);
    assert.deepEqual(data, {});
  } finally {
    globalThis.chrome = previousChrome;
    globalThis.fetch = previousFetch;
  }
});
