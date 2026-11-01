// Acceptance driver only: actual client + actual loopback API, synthetic identity/storage.
import assert from "node:assert/strict";
import { createPairingClient, PairingClientError } from "./client.mjs";
import { harnessEnvironmentAllowed } from "./http-environment.mjs";

const apiOrigin = "https://agent.example.edu",
  canvasOrigin = "https://canvas.example.edu";
const root = "/v1/source-connections/canvas";
const allowedPaths = new Set(
  [
    "pairing",
    "redeem",
    "bind",
    "context",
    "scope",
    "academic/batch",
    "academic/resource",
    "academic/extract",
    ...["begin", "resume", "batch", "resource", "finish"].map(
      (p) => `discovery/${p}`,
    ),
  ].map((p) => `${root}/${p}`),
);
const scenarios = [
  "lost_before",
  "lost_after",
  "resume_replaced",
  "expire_lease",
  "partial_finish",
  "scope_changed",
  "revoke",
  "cross_account",
  "collector_two_page",
  "collector_lost_after",
  "academic_complete",
  "academic_lost_before",
  "academic_lost_after",
  "academic_partial",
  "academic_scope_changed",
  "academic_revoke",
  "academic_cross_account",
  "assignment_collector_lifecycle",
  "assignment_collector_lost_after",
];
let phase = "configuration";
const rejection = (code) => (e) =>
  e instanceof PairingClientError && e.code === code;

try {
  assert.equal(process.argv.length, 2);
  assert.ok(harnessEnvironmentAllowed(process.env));
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk.toString("utf8");
    assert.ok(Buffer.byteLength(input) <= 4096);
  }
  const { loopback, scenario } = JSON.parse(input),
    target = new URL(loopback);
  assert.ok(scenarios.includes(scenario));
  assert.equal(target.protocol, "http:");
  assert.equal(target.hostname, "127.0.0.1");
  assert.ok(
    target.port &&
      !target.username &&
      !target.password &&
      target.pathname === "/" &&
      !target.search &&
      !target.hash,
  );
  let injected = false;
  const batchBodies = [];
  const academicBodies = [];
  const extractionBodies = [];
  let collectionRound = 0;

  async function transport(url, init) {
    const requested = new URL(url);
    assert.equal(requested.origin, apiOrigin);
    assert.ok(allowedPaths.has(requested.pathname));
    assert.ok(
      !requested.search &&
        !requested.hash &&
        !requested.username &&
        !requested.password,
    );
    assert.equal(init.method, "POST");
    assert.equal(init.credentials, "omit");
    assert.equal(init.redirect, "error");
    assert.equal(init.cache, "no-store");
    const isBatch = requested.pathname.endsWith("/discovery/batch");
    const isAcademic = requested.pathname.endsWith("/academic/batch");
    if (isBatch) batchBodies.push(JSON.parse(init.body));
    if (isAcademic) academicBodies.push(JSON.parse(init.body));
    if (requested.pathname.endsWith("/academic/extract"))
      extractionBodies.push(JSON.parse(init.body));
    if (
      isAcademic &&
      !injected &&
      ["academic_lost_before", "academic_cross_account"].includes(scenario)
    ) {
      injected = true;
      throw Error("synthetic academic loss before dispatch");
    }
    if (
      isBatch &&
      !injected &&
      ["lost_before", "resume_replaced"].includes(scenario)
    ) {
      injected = true;
      throw Error("synthetic transport loss before dispatch");
    }
    const response = await fetch(`${target.origin}${requested.pathname}`, init);
    assert.equal(response.headers.get("cache-control"), "no-store");
    if (
      isAcademic &&
      !injected &&
      ["academic_lost_after", "assignment_collector_lost_after"].includes(
        scenario,
      ) &&
      response.ok
    ) {
      injected = true;
      await response.arrayBuffer();
      throw Error(
        "synthetic academic acknowledgment loss after actual server commit",
      );
    }
    if (
      isBatch &&
      !injected &&
      ["lost_after", "collector_lost_after"].includes(scenario) &&
      response.ok
    ) {
      injected = true;
      await response.arrayBuffer();
      throw Error("synthetic acknowledgment loss after actual server commit");
    }
    // Fixture adapter only. Production URL/TLS/origin validation is not changed.
    Object.defineProperty(response, "url", { value: requested.href });
    return response;
  }
  async function request(path, bearer, body) {
    const response = await transport(`${apiOrigin}${path}`, {
      method: "POST",
      credentials: "omit",
      redirect: "error",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
    return { status: response.status, body: await response.json() };
  }
  async function setup(user = "alice", provider = "7") {
    phase = "pairing";
    const data = {};
    const courseRequests = [];
    const assignmentRequests = [];
    const courseStart = `${canvasOrigin}/api/v1/courses?enrollment_state=active&per_page=50`;
    const courseNext = `${courseStart}&page=opaque-2`;
    const storageArea = {
      async setAccessLevel(value) {
        assert.deepEqual(value, { accessLevel: "TRUSTED_CONTEXTS" });
      },
      async get(name) {
        return structuredClone({ [name]: data[name] });
      },
      async set(value) {
        Object.assign(data, structuredClone(value));
      },
      async remove(name) {
        delete data[name];
      },
    };
    const fresh = () =>
      createPairingClient({
        apiOrigin,
        canvasOrigin,
        storageArea,
        fetchImpl: transport,
        canvasFetch: async (url, init) => {
          assert.equal(init.method, "GET");
          assert.equal(init.credentials, "include");
          assert.equal(init.redirect, "error");
          assert.equal(init.cache, "no-store");
          assert.ok(init.signal instanceof AbortSignal);
          if (url === `${canvasOrigin}/api/v1/users/self/profile`)
            return Response.json({ id: provider });
          if (scenario.startsWith("assignment_collector_")) {
            const match = new URL(url).pathname.match(
              /^\/api\/v1\/courses\/(101|102)\/assignments$/,
            );
            if (match) {
              const course = match[1],
                assignment = course === "101" ? 17 : 18;
              assert.equal(
                url,
                `${canvasOrigin}/api/v1/courses/${course}/assignments?per_page=50&override_assignment_dates=true`,
              );
              assignmentRequests.push(url);
              const response = Response.json([
                {
                  id: assignment,
                  course_id: Number(course),
                  name: `Synthetic collection assignment ${assignment}`,
                  description: `<p>Read <strong>carefully</strong> for course ${course}</p><script>PRIVATE_SCRIPT</script><p><a href="/courses/${course}/pages/reference">Reference</a></p>`,
                  due_at:
                    collectionRound === 2 && course === "101"
                      ? "2026-11-03T05:59:00Z"
                      : "2026-11-02T05:59:00Z",
                  unlock_at: null,
                  lock_at: null,
                  points_possible: 20,
                  submission_types: ["online_upload"],
                  rubric: [],
                  published: true,
                },
              ]);
              Object.defineProperty(response, "url", { value: url });
              return response;
            }
          }
          assert.ok(
            scenario.startsWith("collector_") ||
              scenario.startsWith("assignment_collector_"),
          );
          assert.ok([courseStart, courseNext].includes(url));
          courseRequests.push(url);
          const first = url === courseStart;
          const response = Response.json(
            [
              {
                id: first ? 101 : 102,
                name: first
                  ? "Synthetic first course"
                  : "Synthetic second course",
                course_code: first ? "SYN-101" : "SYN-102",
                time_zone: "America/Denver",
                enrollments: [{ enrollment_state: "active" }],
                syllabus_body: "Synthetic excluded field",
              },
            ],
            { headers: first ? { link: `<${courseNext}>; rel="next"` } : {} },
          );
          Object.defineProperty(response, "url", { value: url });
          return response; // No provider network request is permitted.
        },
      });
    const issued = await request(`${root}/pairing`, user, {
      origin: canvasOrigin,
    });
    assert.equal(issued.status, 200);
    const client = fresh();
    await client.redeem({
      code: issued.body.code,
      devicePublicId: `interop-${user}`,
    });
    await client.bindCurrentSession();
    return {
      client,
      fresh,
      data,
      courseRequests,
      assignmentRequests,
      courseStart,
      courseNext,
      record: () => Object.values(data)[0],
    };
  }
  const alice = await setup();
  const page = () => ({
    observed_at: new Date().toISOString(),
    next_cursor: null,
    coverage: { state: "complete", reason: null },
    items: [
      {
        provider_id: "101",
        provider_updated_at: null,
        title: "Synthetic HTTP course",
        reference: `${canvasOrigin}/courses/101`,
        content: "",
        fields: {
          course_code: "SYN-101",
          timezone: "America/Denver",
          enrollment_state: "active",
        },
        coverage: "complete",
        missing: [],
      },
    ],
  });
  async function completeCourses(client) {
    phase = "close_courses";
    await client.finishDiscoveryResource({
      resource_key: "courses",
      outcome: "complete",
      reason: null,
    });
  }
  phase = "begin";
  if (
    !scenario.startsWith("collector_") &&
    !scenario.startsWith("academic_") &&
    !scenario.startsWith("assignment_collector_")
  )
    await alice.client.beginDiscovery();

  if (scenario.startsWith("assignment_collector_")) {
    phase = "assignment_collector_scope";
    const context = await alice.fresh().readCurrentContext();
    assert.equal(
      (
        await request(`${root}/scope`, "alice", {
          connection_id: context.connection_id,
          generation: context.generation,
          mode: "all_active",
          course_ids: [],
          resource_kinds: ["assignments"],
        })
      ).status,
      200,
    );
    for (collectionRound = 0; collectionRound < 3; collectionRound++) {
      phase = "assignment_collector_cycle";
      if (collectionRound > 0) await alice.fresh().beginDiscovery();
      let finished = false;
      for (let tick = 0; tick < 20; tick++) {
        const result = await alice.fresh().collectAssignmentPage();
        if (result.state === "blocked") {
          assert.equal(scenario, "assignment_collector_lost_after");
          assert.equal(result.reason, "discovery_outcome_unknown");
          const captured = structuredClone(
            alice.record().discovery.pending.body,
          );
          assert.equal(alice.assignmentRequests.length, 1);
          assert.equal(extractionBodies.length, 1);
          phase = "assignment_collector_recover";
          assert.equal(
            (await alice.fresh().collectAssignmentPage()).action,
            "recover",
          );
          assert.deepEqual(academicBodies.at(-1), captured);
          assert.equal(alice.assignmentRequests.length, 1);
          assert.equal(extractionBodies.length, 1);
          continue;
        }
        for (const secret of [
          "Synthetic",
          "PRIVATE_SCRIPT",
          "lease_token",
          "ingestion_bearer",
          "subject",
          "checkpoint",
        ])
          assert.ok(!JSON.stringify(result).includes(secret));
        assert.ok(!JSON.stringify(alice.record()).includes("PRIVATE_SCRIPT"));
        if (result.state === "finished") {
          assert.equal(result.coverage, "partial");
          finished = true;
          break;
        }
      }
      assert.equal(finished, true);
      assert.equal(alice.courseRequests.length, (collectionRound + 1) * 2);
      assert.equal(alice.assignmentRequests.length, (collectionRound + 1) * 2);
      assert.equal(extractionBodies.length, (collectionRound + 1) * 2);
      assert.equal(alice.record().discovery.pending, null);
    }
    assert.deepEqual(
      alice.courseRequests,
      Array.from({ length: 3 }, () => [
        alice.courseStart,
        alice.courseNext,
      ]).flat(),
    );
    assert.equal(
      academicBodies.length,
      scenario === "assignment_collector_lost_after" ? 7 : 6,
    );
    assert.equal(new Set(academicBodies.map((body) => body.batch_key)).size, 6);
    assert.ok(
      extractionBodies.every((body) => ["101", "102"].includes(body.course_id)),
    );
  } else if (scenario.startsWith("academic_")) {
    phase = "academic_scope";
    const context = await alice.client.readCurrentContext();
    assert.equal(
      (
        await request(`${root}/scope`, "alice", {
          connection_id: context.connection_id,
          generation: context.generation,
          mode: "all_active",
          course_ids: [],
          resource_kinds: ["assignments"],
        })
      ).status,
      200,
    );
    await alice.fresh().beginDiscovery();
    await alice.fresh().commitDiscoveryPage(page());
    await completeCourses(alice.fresh());
    const assignment = (id, next) => ({
      resource_key: "101/assignments",
      observed_at: new Date().toISOString(),
      next_cursor: next,
      coverage: {
        state: next ? "partial" : "complete",
        reason: next ? "more_pages" : null,
      },
      items: [
        {
          raw: {
            id,
            course_id: 101,
            name: `Synthetic assignment ${id}`,
            description: "Synthetic excluded raw HTML",
            due_at: "2026-11-02T05:59:00Z",
            unlock_at: null,
            lock_at: null,
            points_possible: 20,
            submission_types: ["online_upload"],
            rubric: scenario === "academic_partial" && id === 17 ? null : [],
            published: true,
          },
          extracted: {
            courseId: 101,
            assignmentId: id,
            text: `Synthetic extracted instructions ${id}`,
            coverage: "complete",
            missing: [],
          },
          dateContext: "requesting_student",
        },
      ],
    });
    phase = "academic_first_page";
    if (["academic_scope_changed", "academic_revoke"].includes(scenario)) {
      await assert.rejects(
        alice.fresh().commitAssignmentPage(assignment(17, "opaque-next")),
        rejection(
          scenario === "academic_revoke"
            ? "reconnect_required"
            : "discovery_generation_changed",
        ),
      );
      if (scenario === "academic_revoke") assert.deepEqual(alice.data, {});
      else
        await assert.rejects(
          alice.fresh().retryDiscovery(),
          rejection("discovery_context_changed"),
        );
    } else {
      const lost = [
        "academic_lost_before",
        "academic_lost_after",
        "academic_cross_account",
      ].includes(scenario);
      if (lost) {
        await assert.rejects(
          alice.fresh().commitAssignmentPage(assignment(17, "opaque-next")),
          rejection("discovery_outcome_unknown"),
        );
        const capture = structuredClone(alice.record().discovery.pending.body);
        assert.deepEqual(academicBodies[0], capture);
        assert.ok(
          !JSON.stringify(alice.record()).includes("excluded raw HTML"),
        );
        if (scenario === "academic_cross_account") {
          phase = "academic_cross_account_denial";
          const bob = await setup("bob", "8");
          for (const [path, body] of [
            ["batch", capture],
            [
              "resource",
              {
                scan_id: capture.scan_id,
                generation: capture.generation,
                lease_token: capture.lease_token,
                expected_checkpoint: capture.expected_checkpoint,
                finish_key: "bob-cannot-close-alice",
                resource_key: "101/assignments",
                outcome: "complete",
                reason: null,
              },
            ],
          ]) {
            const denied = await request(
              `${root}/academic/${path}`,
              bob.record().ingestion_bearer,
              body,
            );
            assert.equal(denied.status, 401);
            for (const secret of [
              capture.scan_id,
              capture.envelope.items[0].content,
              alice.record().ingestion_bearer,
            ])
              assert.ok(!JSON.stringify(denied.body).includes(secret));
          }
          assert.deepEqual(alice.record().discovery.pending.body, capture);
        }
        if (scenario === "academic_lost_after") {
          phase = "academic_resume_accepted_page";
          const resumed = await alice.fresh().resumeDiscovery();
          assert.equal(resumed.checkpoint.resource, "101/assignments");
          assert.equal(resumed.checkpoint.sequence, 2);
        }
        phase = "academic_exact_replay";
        const recovered = await alice.fresh().retryDiscovery();
        assert.equal(recovered.checkpoint.sequence, 2);
        const resent = academicBodies.at(-1);
        if (scenario === "academic_lost_after") {
          assert.notEqual(resent.lease_token, capture.lease_token);
          assert.deepEqual(
            { ...resent, lease_token: capture.lease_token },
            capture,
          );
        } else assert.deepEqual(resent, capture);
        assert.equal(alice.record().discovery.academic.page_count, 1);
      } else
        await alice.fresh().commitAssignmentPage(assignment(17, "opaque-next"));
      phase = "academic_terminal_page";
      const result = await alice
        .fresh()
        .commitAssignmentPage(assignment(18, null));
      assert.equal(result.checkpoint.sequence, 3);
      assert.equal(alice.record().discovery.academic.seen_count, 2);
      for (const secret of [
        "Synthetic",
        "subject",
        "lease_token",
        "ingestion_bearer",
      ])
        assert.ok(!JSON.stringify(result).includes(secret));
      const finish = {
        resource_key: "101/assignments",
        outcome: "complete",
        reason: null,
      };
      if (scenario === "academic_partial") {
        phase = "academic_incomplete_denial";
        await assert.rejects(
          alice.fresh().finishAssignmentResource(finish),
          rejection("invalid_assignment_input"),
        );
        assert.equal(alice.record().discovery.pending, null);
        const record = alice.record(),
          j = record.discovery;
        const denied = await request(
          `${root}/academic/resource`,
          record.ingestion_bearer,
          {
            scan_id: j.scan.scan_id,
            generation: j.binding.generation,
            lease_token: j.scan.lease_token,
            expected_checkpoint: j.scan.checkpoint,
            finish_key: "cannot-hide-earlier-gap",
            ...finish,
          },
        );
        assert.equal(denied.status, 409);
        assert.equal(denied.body.detail.code, "incomplete_resource");
        finish.outcome = "partial";
        finish.reason = "extraction_failed";
      }
      phase = "academic_resource_manifest";
      await alice.fresh().finishAssignmentResource(finish);
      phase = "academic_scan_finish";
      assert.equal(
        (await alice.fresh().finishDiscovery()).coverage,
        scenario === "academic_partial" ? "partial" : "complete",
      );
      assert.equal(
        new Set(academicBodies.map((body) => body.batch_key)).size,
        2,
      );
      assert.equal(alice.courseRequests.length, 0); // Inputs are synthetic; no source collection claim.
    }
  } else if (scenario.startsWith("collector_")) {
    phase = "collector_scope";
    const context = await alice.client.readCurrentContext();
    const selected = await request(`${root}/scope`, "alice", {
      connection_id: context.connection_id,
      generation: context.generation,
      mode: "all_active",
      course_ids: [],
      resource_kinds: ["assignments"],
    });
    assert.equal(selected.status, 200);
    phase = "collector_begin";
    assert.equal((await alice.client.collectCoursePage()).action, "begin");
    assert.equal(alice.courseRequests.length, 0);
    phase = "collector_first_page";
    const first = await alice.fresh().collectCoursePage();
    if (scenario === "collector_lost_after") {
      assert.deepEqual(first, {
        state: "blocked",
        reason: "discovery_outcome_unknown",
      });
      const capture = structuredClone(alice.record().discovery.pending.body);
      assert.equal(alice.courseRequests.length, 1);
      phase = "collector_recovery";
      const recovered = await alice.fresh().collectCoursePage();
      assert.equal(recovered.action, "recover");
      assert.equal(recovered.seen_count, 1);
      assert.equal(alice.courseRequests.length, 1);
      assert.deepEqual(batchBodies[0], capture);
      assert.deepEqual(batchBodies[1], capture);
    } else {
      assert.equal(first.action, "page");
      assert.equal(first.seen_count, 1);
    }
    phase = "collector_second_page";
    const second = await alice.fresh().collectCoursePage();
    assert.equal(second.action, "page");
    assert.equal(second.seen_count, 2);
    assert.deepEqual(alice.courseRequests, [
      alice.courseStart,
      alice.courseNext,
    ]);
    assert.equal(new Set(batchBodies.map((body) => body.batch_key)).size, 2);
    assert.ok(
      batchBodies.every((body) =>
        body.envelope.items.every((item) => item.content === ""),
      ),
    );
    phase = "collector_close_courses";
    assert.equal(
      (await alice.fresh().collectCoursePage()).action,
      "close_courses",
    );
    phase = "collector_awaiting_academic_resources";
    for (let i = 0; i < 2; i++) {
      const waiting = await alice.fresh().collectCoursePage();
      assert.equal(waiting.state, "awaiting_resources");
      assert.equal(waiting.open_resources, 2);
      assert.equal(waiting.coverage, null);
      const serialized = JSON.stringify(waiting);
      for (const forbidden of [
        "Synthetic",
        "subject",
        "lease_token",
        "checkpoint",
        "cursor",
        canvasOrigin,
      ])
        assert.ok(!serialized.includes(forbidden));
    }
    assert.equal(alice.courseRequests.length, 2);
    assert.equal(alice.record().discovery.pending, null);
    await assert.rejects(
      alice.fresh().finishDiscovery(),
      rejection("discovery_resources_open"),
    );
    assert.equal(alice.record().discovery.pending, null);
    const record = alice.record(),
      j = record.discovery;
    const denied = await request(
      `${root}/discovery/finish`,
      record.ingestion_bearer,
      {
        scan_id: j.scan.scan_id,
        generation: j.binding.generation,
        lease_token: j.scan.lease_token,
        finish_key: "collector-incomplete-denied",
      },
    );
    assert.equal(denied.status, 409);
    assert.equal(denied.body.detail.code, "resources_open");
  } else if (scenario === "cross_account") {
    const bob = await setup("bob", "8"),
      record = alice.record(),
      j = record.discovery;
    phase = "cross_account_denials";
    assert.equal(
      (
        await request(`${root}/scope`, "bob", {
          connection_id: j.binding.connection_id,
          generation: j.binding.generation,
          mode: "explicit_set",
          course_ids: [],
          resource_kinds: [],
        })
      ).status,
      404,
    );
    const attempted = await request(
      `${root}/discovery/begin`,
      bob.record().ingestion_bearer,
      {
        connection_id: j.binding.connection_id,
        generation: j.binding.generation,
        subject: "7",
        scope_revision: j.binding.scope_revision,
        begin_key: "not-owned",
      },
    );
    assert.equal(attempted.status, 401);
    assert.equal(
      (
        await request(
          `${root}/discovery/resume`,
          bob.record().ingestion_bearer,
          {
            scan_id: j.scan.scan_id,
            generation: j.binding.generation,
            resume_key: "not-owned-resume",
          },
        )
      ).status,
      401,
    );
    assert.ok(
      !JSON.stringify(attempted.body).includes(j.binding.connection_id),
    );
  } else if (["scope_changed", "revoke"].includes(scenario)) {
    phase = "control_race";
    await assert.rejects(
      alice.client.commitDiscoveryPage(page()),
      rejection(
        scenario === "revoke"
          ? "reconnect_required"
          : "discovery_generation_changed",
      ),
    );
    if (scenario === "revoke") assert.deepEqual(alice.data, {});
    else
      await assert.rejects(
        alice.fresh().retryDiscovery(),
        rejection("discovery_context_changed"),
      );
  } else {
    phase = "commit";
    if (["lost_before", "lost_after", "resume_replaced"].includes(scenario)) {
      await assert.rejects(
        alice.client.commitDiscoveryPage(page()),
        rejection("discovery_outcome_unknown"),
      );
      const capture = structuredClone(
        alice.record().discovery.pending.body.envelope,
      );
      if (scenario === "resume_replaced") {
        phase = "replace_lease";
        const record = alice.record(),
          j = record.discovery;
        assert.equal(
          (
            await request(`${root}/discovery/resume`, record.ingestion_bearer, {
              scan_id: j.scan.scan_id,
              generation: j.binding.generation,
              resume_key: "other-writer",
            })
          ).status,
          200,
        );
        await assert.rejects(
          alice.fresh().retryDiscovery(),
          rejection("discovery_lease_replaced"),
        );
        await alice.fresh().resumeDiscovery();
      }
      phase = "retry";
      const result = await alice.fresh().retryDiscovery();
      assert.equal(result.seen_count, 1);
      assert.equal(result.checkpoint.sequence, 1);
      assert.ok(
        batchBodies.every(
          (body) => JSON.stringify(body.envelope) === JSON.stringify(capture),
        ),
      );
      assert.ok(
        batchBodies.every((body) => body.batch_key === capture.batch_key),
      );
    } else if (scenario === "expire_lease") {
      await assert.rejects(
        alice.client.commitDiscoveryPage(page()),
        rejection("discovery_lease_expired"),
      );
      await alice.fresh().resumeDiscovery();
      await alice.fresh().retryDiscovery();
    } else await alice.client.commitDiscoveryPage(page());
    await completeCourses(alice.fresh());
    phase = "finish";
    assert.equal((await alice.fresh().finishDiscovery()).coverage, "complete");

    if (scenario === "partial_finish") {
      phase = "scope";
      const record = alice.record(),
        context = await alice.client.readCurrentContext();
      const selected = await request(`${root}/scope`, "alice", {
        connection_id: context.connection_id,
        generation: context.generation,
        mode: "explicit_set",
        course_ids: ["101"],
        resource_kinds: ["assignments"],
      });
      assert.equal(selected.status, 200);
      assert.ok(selected.body.generation > record.connection.generation);
      await alice.fresh().beginDiscovery();
      await alice.fresh().commitDiscoveryPage(page());
      await completeCourses(alice.fresh());
      phase = "partial_finish";
      await assert.rejects(
        alice.fresh().finishDiscovery(),
        rejection("discovery_resources_open"),
      );
      assert.equal(alice.record().discovery.pending, null);
      await alice.fresh().finishDiscoveryResource({
        resource_key: "101/assignments",
        outcome: "unsupported",
        reason: "unsupported_format",
      });
      assert.equal((await alice.fresh().finishDiscovery()).coverage, "partial");
    }
  }
  process.stdout.write(JSON.stringify({ ok: true, scenario }));
} catch (error) {
  const code =
    error instanceof PairingClientError ? error.code : "assertion_failed";
  process.stdout.write(JSON.stringify({ ok: false, phase, code }));
  process.exitCode = 1;
}
