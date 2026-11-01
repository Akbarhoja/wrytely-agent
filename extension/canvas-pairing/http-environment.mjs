// Acceptance-harness name policy only. Parent env filtering remains stricter.
const inherited = new Set([
  "PATH",
  "SYSTEMROOT",
  "WINDIR",
  "COMSPEC",
  "PATHEXT",
  "TEMP",
  "TMP",
  "LANG",
  "LC_ALL",
]);

export function harnessEnvironmentAllowed(
  environment,
  platform = process.platform,
) {
  return Object.keys(environment).every(
    (name) =>
      inherited.has(name.toUpperCase()) ||
      (platform === "darwin" && name === "__CF_USER_TEXT_ENCODING"),
  );
}
