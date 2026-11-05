"""Operator-only synthetic fixture for file acceptance, never a Canvas substitute.

No automatic entrypoint, credentials, inference or delivery. A separately approved
operator supplies a verified owner. Only explicitly labelled synthetic source/work
is created in the original Store. Real course records and readiness are untouched.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from contracts.document_artifacts import CoursePolicyV2, RubricItemV2
from contracts.models import SourceObservation, TaskLease

POLICY = "AI drafting is permitted with disclosure for this synthetic practice exercise."
RUBRIC = "Compare the participant counts in Source A and Source B."
CLAIM_A = "Source A reports 10 participants."
CLAIM_B = "Source B reports 12 participants."
DISCLOSURE = "AI-generated synthetic practice. Not coursework."
TEXT = "\n".join(
    [
        "SYNTHETIC PRACTICE — invented test data, not a real course.",
        POLICY,
        RUBRIC,
        CLAIM_A,
        CLAIM_B,
        "Required disclosure: " + DISCLOSURE,
    ]
)


def prepare_practice(store, verified_user, *, approved=False):
    """Explicit rehearsal setup; no model decisions/checks are fabricated."""
    if approved is not True:
        raise ValueError("Separate synthetic-fixture approval required")
    key = "practice-file-" + str(uuid4())
    with store._atomic_connection() as conn:
        source = store.observe_source(
            verified_user,
            SourceObservation(
                source_key=key,
                external_revision="synthetic-v1",
                title="SYNTHETIC PRACTICE — file acceptance",
                reference="synthetic:wrytely-file-acceptance",
                coverage="snapshot",
                content=TEXT,
                retrieved_at=datetime.now(UTC),
            ),
        )
        duty = store.create_bound_responsibility(
            verified_user,
            "Prepare an ungraded SYNTHETIC PRACTICE comparison using only the two invented "
            "participant counts. Include the required disclosure and exact citations. "
            "This is file acceptance, not real coursework; do not use other course context.",
            key,
            source_ids=[source["source_id"]],
            max_steps=3,
        )
        # Operator task setup is explicitly labelled; no invented model/planner result.
        conn.execute(
            "UPDATE wrytely_agent.tasks SET status='blocked',last_error='synthetic_fixture_setup' "
            "WHERE agent_id=%s AND responsibility_id=%s AND kind='plan' AND status='ready'",
            (duty["agent_id"], duty["id"]),
        )
        conn.execute(
            "UPDATE wrytely_agent.responsibilities SET steps_created=1 WHERE id=%s",
            (duty["id"],),
        )
        task = store._responsibility_task(
            conn,
            duty["agent_id"],
            duty["id"],
            "academic",
            duty["objective"],
            "synthetic-first-file",
        )

    def evidence(quote):
        return dict(kind="legacy", version_id=source["id"], quote=quote)

    return {
        "duty": duty,
        "source": source,
        "task_id": task,
        "policy": CoursePolicyV2(status="disclosure_required", evidence=evidence(POLICY)),
        "rubric": [RubricItemV2(evidence=evidence(RUBRIC))],
    }


def claim_practice_task(store, verified_user, task_id, duty_id):
    """Claim exactly one newly queued fixture task; never a global queue selector.

    Refuses an earlier attempt, expired/running work, a different responsibility,
    paused owner or concurrent owner task. Original Store fences still authorize
    every model checkpoint, source read and artifact commit afterward.
    """
    task_id, duty_id = UUID(str(task_id)), UUID(str(duty_id))
    with store._atomic_connection() as conn:
        agent = conn.execute(
            "SELECT id,paused FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE",
            (verified_user,),
        ).fetchone()
        if not agent or agent["paused"]:
            raise ValueError("Active verified fixture owner required")
        row = conn.execute(
            "SELECT t.* FROM wrytely_agent.tasks t JOIN wrytely_agent.responsibilities r "
            "ON r.id=t.responsibility_id AND r.agent_id=t.agent_id "
            "WHERE t.id=%s AND t.agent_id=%s AND r.id=%s AND r.status='active' "
            "AND r.request_key LIKE 'practice-file-%%' AND t.kind='academic' "
            "AND t.status='ready' AND t.attempts=0 AND t.available_at<=clock_timestamp() "
            "AND t.memory_revision=r.memory_revision FOR UPDATE OF t",
            (task_id, agent["id"], duty_id),
        ).fetchone()
        if (
            row is None
            or conn.execute(
                "SELECT 1 FROM wrytely_agent.tasks WHERE agent_id=%s AND status='running'",
                (agent["id"],),
            ).fetchone()
        ):
            raise ValueError("New nonconcurrent fixture task required; no retry")
        token = uuid4()
        conn.execute(
            "UPDATE wrytely_agent.tasks SET status='running',attempts=1,lease_token=%s,"
            "lease_until=clock_timestamp()+interval '300 seconds' WHERE id=%s",
            (token, task_id),
        )
        lease = TaskLease(task_id, agent["id"], verified_user, token, 1, row["message_id"])
        store.event(lease, "operator_synthetic_fixture_claim", {"scope": "practice_file_only"})
        return lease
