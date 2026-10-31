// No import-time provider IO. Private config is an explicit operator-owned local file.
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { FILE_ORIGIN, validateScope } from "./details.mjs";
const [configPath, outputPath] = process.argv.slice(2);
if (!configPath || !outputPath)
  throw Error("Supply private config path and ignored output directory");
const config = JSON.parse(await readFile(configPath, "utf8"));
const { origin } = validateScope(config);
const output = resolve(outputPath);
await mkdir(output, { recursive: true });
for (const file of [
  "probe.mjs",
  "details.mjs",
  "worker.mjs",
  "popup.html",
  "popup.mjs",
])
  await copyFile(new URL(file, import.meta.url), resolve(output, file));
await writeFile(
  resolve(output, "scope.mjs"),
  `export const config = ${JSON.stringify(config)};\n`,
  { mode: 0o600 },
);
await writeFile(
  resolve(output, "manifest.json"),
  JSON.stringify(
    {
      manifest_version: 3,
      name: "Wrytely Canvas feasibility (local diagnostic)",
      version: "0.0.2",
      description:
        "Operator-only read-only document/rubric check; private local counts, no uploads.",
      host_permissions: [
        `${origin}/*`,
        ...(config.fileSamples.length ? [`${FILE_ORIGIN}/*`] : []),
      ],
      background: { service_worker: "worker.mjs", type: "module" },
      action: {
        default_title: "Wrytely Canvas access check",
        default_popup: "popup.html",
      },
    },
    null,
    2,
  ) + "\n",
);
console.info(
  "Prepared v2 diagnostic; no installation, permissions or source reads performed.",
);
