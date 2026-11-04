export const preparationId = "00000000-0000-4000-8000-000000000001";
export const objectId = "00000000-0000-4000-8000-000000000002";
export const preparation = () => ({
  id: preparationId,
  created_at: "2026-11-04T12:00:00Z",
  key: "a".repeat(64),
  object_id: objectId,
  title: "Synthetic hardware preparation",
  kind: "preparation_checklist" as const,
  notice:
    "Preparation checklist only, not a completed or checked assignment. Read the original instructions; missing material may change these steps. Perform physical work yourself and provide actual results. This checklist does not establish permission for AI-written submissions.",
  current: true,
  excerpts: [
    {
      object_id: objectId,
      quote: "Build and test the circuit yourself. Record your actual measurements.",
      kind: "student_action" as const,
    },
  ],
  questions: ["Can you access the linked manual?", "Have you collected your actual measurements?"],
  evidence: [
    {
      object_id: objectId,
      observation_id: "00000000-0000-4000-8000-000000000003",
      version_id: null,
      coverage: "partial",
      resource_coverage: "partial",
      missing: ["linked_content_unread", "policy_not_fully_read"],
      unread_continuation: true,
    },
  ],
});
