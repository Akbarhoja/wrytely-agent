import assert from "node:assert/strict";
import test from "node:test";
import { readModulePage, prepareModuleDocuments } from "./module-reader.mjs";
const origin = "https://canvas.example.edu";
test("module items always paginate separately, including quiz references without visiting them", async () => {
  const calls = [];
  const get = async (path, query) => {
    calls.push(path + query);
    if (path.endsWith("/modules"))
      return {
        data: [
          {
            id: 90,
            name: "Module",
            items: [{ id: 999, title: "Incomplete inline sample" }],
            _wrytely_module: "forged",
          },
        ],
        link: "",
      };
    return {
      data: [
        {
          id: 91,
          module_id: 90,
          title: "Quiz reference",
          type: "Quiz",
          content_id: 80,
          html_url: origin + "/courses/101/quizzes/80",
          _wrytely_module: "forged",
        },
      ],
      link: "",
    };
  };
  const first = await readModulePage({
    course: "101",
    origin,
    cursor: null,
    get,
  });
  assert.equal(first.data[0]._wrytely_module, null);
  const second = await readModulePage({
    course: "101",
    origin,
    cursor: first.next_cursor,
    get,
  });
  assert.equal(second.data[0]._wrytely_module, "90");
  assert.equal(second.next_cursor, null);
  const doc = prepareModuleDocuments({
    resource_key: "101/modules",
    origin,
    page: second,
  }).documents[0];
  assert.equal(doc.owner_object.kind, "module_item");
  assert.equal(doc.object_fields.content_id, "80");
  assert.deepEqual(calls, [
    "/api/v1/courses/101/modules?per_page=4",
    "/api/v1/courses/101/modules/90/items?per_page=4",
  ]);
});
test("cross-course or cross-origin module continuation fails before IO", async () => {
  for (const cursor of [
    origin + "/api/v1/courses/102/modules?per_page=4",
    "https://evil.example/api/v1/courses/101/modules?per_page=4",
  ])
    await assert.rejects(
      readModulePage({
        course: "101",
        origin,
        cursor,
        get: () => assert.fail("must not fetch"),
      }),
      { code: "unsafe_pagination" },
    );
});
test("module item parent must match queued module", async () => {
  const first = await readModulePage({
    course: "101",
    origin,
    cursor: null,
    get: async () => ({ data: [{ id: 90, name: "Module" }], link: "" }),
  });
  await assert.rejects(
    readModulePage({
      course: "101",
      origin,
      cursor: first.next_cursor,
      get: async () => ({ data: [{ id: 91, module_id: 99 }], link: "" }),
    }),
    { code: "invalid_collection" },
  );
});
