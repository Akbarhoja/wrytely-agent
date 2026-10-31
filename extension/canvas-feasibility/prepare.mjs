import { mkdir, copyFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { checkedOrigin } from "./probe.mjs";

// Run only after the exact institution/course scope is authorized. Output is ignored.
const [originInput, ...courseIds] = process.argv.slice(2);
const origin = checkedOrigin(originInput);
if (
  !courseIds.length ||
  courseIds.length > 2 ||
  courseIds.some((x) => !/^[1-9][0-9]*$/.test(x))
) {
  throw new Error(
    "Supply one or two consenting numeric course IDs for this diagnostic only",
  );
}
const output = new URL("./unpacked/", import.meta.url);
await mkdir(output, { recursive: true });
for (const file of ["probe.mjs", "worker.mjs"]) {
  await copyFile(new URL(file, import.meta.url), new URL(file, output));
}
await writeFile(
  new URL("scope.mjs", output),
  `export const config = ${JSON.stringify({ origin, courseIds })};\n`,
);
await writeFile(
  new URL("manifest.json", output),
  JSON.stringify(
    {
      manifest_version: 3,
      name: "Wrytely Canvas feasibility (local diagnostic)",
      version: "0.0.1",
      description:
        "Operator-triggered read-only probe; redacted counts, no source upload.",
      host_permissions: [`${origin}/*`],
      background: { service_worker: "worker.mjs", type: "module" },
      action: { default_title: "Run consenting Canvas feasibility check" },
    },
    null,
    2,
  ) + "\n",
);
console.info("Prepared local diagnostic:", fileURLToPath(output));
