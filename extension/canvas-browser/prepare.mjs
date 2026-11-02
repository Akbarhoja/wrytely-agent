import {
  copyFile,
  lstat,
  mkdir,
  readFile,
  realpath,
  writeFile,
} from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { checkedOrigin } from "../canvas-feasibility/probe.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const source = fileURLToPath(new URL("./", import.meta.url));
const runtimeFiles = [
  "canvas-pairing/host-events.mjs",
  "canvas-pairing/host.mjs",
  "canvas-pairing/client.mjs",
  "canvas-pairing/discovery.mjs",
  "canvas-pairing/document-journal.mjs",
  "canvas-pairing/document-reader.mjs",
  "canvas-pairing/file-documents.mjs",
  "canvas-pairing/file-storage.mjs",
  "canvas-pairing/module-reader.mjs",
  "canvas-pairing/discussion-thread.mjs",
  "canvas-pairing/document-collector.mjs",
  "canvas-pairing/submission-documents.mjs",
  "canvas/document-parts.mjs",
  "canvas-pairing/collector.mjs",
  "canvas-pairing/assignment-page.mjs",
  "canvas-feasibility/probe.mjs",
  "canvas/assignment-observation.mjs",
  "canvas/source-digest.mjs",
];
const uiFiles = [
  "popup.html",
  "options.html",
  "styles.css",
  "ui.mjs",
  "boot.mjs",
  "worker.mjs",
  "fonts/plus-jakarta-sans-latin.woff2",
  "fonts/OFL.txt",
];
function fail(code) {
  throw Object.assign(new Error(code), { code });
}
function origin(value) {
  try {
    if (
      typeof value !== "string" ||
      checkedOrigin(value) !== value ||
      !/^https:\/\/[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(value)
    )
      fail("invalid_origin");
    return value;
  } catch {
    fail("invalid_origin");
  }
}
async function noLinks(path) {
  const rel = relative(root, path);
  if (rel.startsWith("..") || resolve(path) === resolve(root))
    fail("invalid_output");
  let current = root;
  for (const part of rel.split(sep)) {
    current = resolve(current, part);
    try {
      const item = await lstat(current);
      if (item.isSymbolicLink()) fail("symlink_output");
      if (!item.isDirectory()) fail("invalid_output");
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
    }
  }
}
export async function prepareCanvasPackage({
  apiOrigin,
  canvasOrigin,
  output,
}) {
  apiOrigin = origin(apiOrigin);
  canvasOrigin = origin(canvasOrigin);
  if (typeof output !== "string" || !output.trim()) fail("invalid_output");
  const allowed = resolve(root, ".local/canvas-packages"),
    target = resolve(output),
    rel = relative(allowed, target);
  if (!rel || rel.startsWith("..") || resolve(allowed, rel) !== target)
    fail("invalid_output");
  await noLinks(target);
  try {
    await lstat(target);
    fail("output_exists");
  } catch (e) {
    if (e.code !== "ENOENT") throw e;
  }
  const css = await readFile(resolve(root, "web/app/globals.css"), "utf8");
  const initial = /^:root\s*\{([^}]+)\}/.exec(css)?.[1];
  if (!initial) fail("canonical_tokens_missing");
  const tokenNames = [
    "bg",
    "surface",
    "text",
    "muted",
    "border",
    "green",
    "tint",
    "sidebar",
    "danger",
    "focus",
  ];
  const tokens = tokenNames.map((name) => {
    const value = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`).exec(
      initial,
    )?.[1];
    if (!value) fail("canonical_tokens_missing");
    return `  --${name}: ${value};`;
  });
  // Validate all source assets before reserving a fresh output directory.
  for (const file of uiFiles) await readFile(resolve(source, file));
  for (const file of runtimeFiles)
    await readFile(resolve(root, "extension", file));
  await mkdir(dirname(target), { recursive: true });
  await noLinks(dirname(target));
  await mkdir(target); // Exclusive reservation: never overwrite or remove an existing package.
  if (
    relative(await realpath(allowed), await realpath(target)).startsWith("..")
  )
    fail("invalid_output");
  for (const file of [...uiFiles, ...runtimeFiles]) {
    const dest = resolve(target, file);
    await mkdir(dirname(dest), { recursive: true });
    await copyFile(
      resolve(
        uiFiles.includes(file) ? source : resolve(root, "extension"),
        file,
      ),
      dest,
    );
  }
  await writeFile(
    resolve(target, "config.mjs"),
    `export const config = Object.freeze(${JSON.stringify({ apiOrigin, canvasOrigin })});\n`,
    { flag: "wx" },
  );
  await writeFile(
    resolve(target, "tokens.css"),
    `:root {\n${tokens.join("\n")}\n  color-scheme: light;\n}\n`,
    { flag: "wx" },
  );
  const hosts = [
    ...new Set([
      apiOrigin,
      canvasOrigin,
      "https://inst-fs-iad-prod.inscloudgate.net",
      "https://cdn.inst-fs-iad-prod.inscloudgate.net",
    ]),
  ];
  const manifest = {
    manifest_version: 3,
    name: "Wrytely Canvas collection (development)",
    version: "0.1.0",
    minimum_chrome_version: "120",
    description:
      "Private student-controlled Canvas collection; inactive until explicitly enabled.",
    permissions: ["storage", "alarms", "webRequest"],
    host_permissions: hosts.map((value) => `${value}/*`),
    background: { service_worker: "worker.mjs", type: "module" },
    action: {
      default_popup: "popup.html",
      default_title: "Canvas collection · Wrytely",
    },
    options_page: "options.html",
    content_security_policy: {
      extension_pages: `default-src 'self'; script-src 'self'; object-src 'none'; connect-src ${hosts.join(" ")}; style-src 'self'; font-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none';`,
    },
  };
  // Manifest is last: a partial build is not presented as an installable package.
  await writeFile(
    resolve(target, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
    { flag: "wx" },
  );
  return { manifest, output: target };
}
if (
  process.argv[1] &&
  pathToFileURL(resolve(process.argv[1])).href === import.meta.url
) {
  try {
    if (process.argv.length !== 5)
      fail("usage: prepare.mjs API_ORIGIN CANVAS_ORIGIN FRESH_OUTPUT");
    const [apiOrigin, canvasOrigin, output] = process.argv.slice(2);
    await prepareCanvasPackage({ apiOrigin, canvasOrigin, output });
    console.info(
      "Prepared inactive local package. No installation or access occurred.",
    );
  } catch {
    console.error(
      "Package preparation failed. Check origins and use a fresh directory under .local/canvas-packages.",
    );
    process.exitCode = 1;
  }
}
