import assert from "node:assert/strict";
import test from "node:test";
import { harnessEnvironmentAllowed } from "./http-environment.mjs";

test("the explicit parent names are valid on every supported host", () => {
  const env = Object.fromEntries(
    [
      "PATH",
      "SYSTEMROOT",
      "WINDIR",
      "COMSPEC",
      "PATHEXT",
      "TEMP",
      "TMP",
      "LANG",
      "LC_ALL",
    ].map((k) => [k, "synthetic"]),
  );
  for (const platform of ["darwin", "linux", "win32"])
    assert.equal(harnessEnvironmentAllowed(env, platform), true);
});
test("Darwin may add only its exact runtime encoding name after spawn", () => {
  assert.equal(
    harnessEnvironmentAllowed(
      { PATH: "synthetic", __CF_USER_TEXT_ENCODING: "ignored" },
      "darwin",
    ),
    true,
  );
  for (const platform of ["linux", "win32"])
    assert.equal(
      harnessEnvironmentAllowed(
        { __CF_USER_TEXT_ENCODING: "ignored" },
        platform,
      ),
      false,
    );
});
for (const platform of ["darwin", "linux", "win32"]) {
  for (const name of [
    "WRYTELY_TEST_PARENT_CANARY",
    "OPENAI_API_KEY",
    "DATABASE_URL",
    "__CF_USER_TEXT_ENCODING_EXTRA",
    "__cf_user_text_encoding",
    "CANVAS_TOKEN",
  ]) {
    test(`${platform} rejects unexpected name ${name}`, () =>
      assert.equal(
        harnessEnvironmentAllowed(
          { PATH: "synthetic", [name]: "excluded" },
          platform,
        ),
        false,
      ));
  }
}
test("the name policy never reads environment values", () => {
  const env = {};
  Object.defineProperty(env, "__CF_USER_TEXT_ENCODING", {
    enumerable: true,
    get() {
      throw Error("must not read");
    },
  });
  assert.equal(harnessEnvironmentAllowed(env, "darwin"), true);
});
