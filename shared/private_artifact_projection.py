"""Strict, content-bounded student projections of existing internal v2 artifacts."""

import json
from datetime import UTC, datetime, timedelta

from contracts.artifacts import Assessment
from contracts.document_artifacts import CoursePolicyV2, RubricItemV2
from shared.academic_reads import student_json

LIMITS = "Saved checks and current inspection status are not permission to draft, send or submit."
ERROR_CODES = frozenset(
    "assessment_coverage_mismatch citation_missing_or_stale citations_missing "
    "cited_claim_not_in_draft claims_not_supported course_policy_not_permitting_draft "
    "disclosure_assessment_failed disclosure_format_ambiguous disclosure_missing_from_body "
    "disclosure_must_be_separate disclosure_text_mismatch document_evidence_missing_or_stale "
    "document_evidence_failed_at_commit evidence_freshness_failed_at_commit invalid_assessment "
    "policy_assessment_failed policy_evidence_missing_or_stale rubric_evidence_missing_or_stale "
    "rubric_incomplete rubric_not_covered typed_evidence_missing_or_stale "
    "typed_evidence_failed_at_commit uncited_claims word_count_bounds_conflict "
    "word_count_out_of_range word_count_requirement_invalid word_count_requirement_unparsed".split()
)


class PrivateArtifactReadLimit(Exception):
    """A private response cannot be returned intact inside its byte budget."""


def bounded(value):
    value = student_json(value)
    if len(json.dumps(value, ensure_ascii=False).encode()) > 1024 * 1024:
        raise PrivateArtifactReadLimit("read_limit")
    return value


def project_check(row, artifact_revision, claim_count):
    """Return validated fields only; malformed checks never look passed."""
    if row is None:
        return None
    raw = row["report"]
    try:
        bounded(raw)
        errors = raw["errors"]
        if (
            row["memory_revision"] != artifact_revision
            or type(raw.get("evidence_schema")) is not int
            or raw["evidence_schema"] != 2
            or type(raw["passed"]) is not bool
            or raw["passed"] != row["passed"]
            or type(errors) is not list
            or len(errors) > 100
            or any(type(code) is not str or code not in ERROR_CODES for code in errors)
            or (raw["passed"] and errors)
            or type(raw["rubric"]) is not list
            or len(raw["rubric"]) > 30
        ):
            return None
        policy = CoursePolicyV2.model_validate(raw["policy"]).model_dump(mode="json")
        rubric = [RubricItemV2.model_validate(r).model_dump(mode="json") for r in raw["rubric"]]
        assessment = (
            Assessment.model_validate(raw["assessment"], strict=True).model_dump(mode="json")
            if raw["assessment"] is not None
            else None
        )
        if raw["passed"] and (
            assessment is None
            or not rubric
            or policy["status"] not in ("permitted", "disclosure_required")
            or not assessment["policy_allows_drafting"]
            or not assessment["disclosure_satisfied"]
            or not assessment["rubric_complete"]
            or assessment["uncited_claims"]
            or any(v != "supported" for v in assessment["claim_support"])
            or any(v != "covered" for v in assessment["rubric_coverage"])
            or len(assessment["rubric_coverage"]) != len(rubric)
            or len(assessment["claim_support"]) != claim_count
        ):
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "memory_revision": row["memory_revision"],
            "report": dict(
                passed=raw["passed"],
                errors=list(errors),
                assessment=assessment,
                policy=policy,
                rubric=rubric,
                limits=LIMITS,
            ),
        }
    except (KeyError, TypeError, ValueError, AttributeError, PrivateArtifactReadLimit):
        return None


def cursor(value):
    if value is None:
        return None
    from uuid import UUID

    try:
        if type(value) is not dict or value.keys() != {"created_at", "id"}:
            raise ValueError()
        identifier = value["id"]
        if type(identifier) is not str or str(UUID(identifier)) != identifier:
            raise ValueError()
        at = value["created_at"]
        if type(at) is str and len(at) <= 40:
            at = datetime.fromisoformat(at)
        if not isinstance(at, datetime) or at.utcoffset() != timedelta(0):
            raise ValueError()
        return at.astimezone(UTC), UUID(identifier)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid artifact cursor") from None


def status(proofs, *, now, memory_stale=False, check_available=True):
    reasons = set()
    states = set()
    if memory_stale:
        states.add("historical")
        reasons.add("memory_revision_changed")
    if not check_available:
        states.add("unverified")
        reasons.add("check_unavailable")
    if not proofs:
        states.add("unverified")
        reasons.add("evidence_missing")
    for proof in proofs:
        source = proof["source"]
        fresh = source["freshness"]
        if fresh["usable"] and fresh["expires_at"] < now:
            fresh.update(usable=False, reason="too_old")
        if not proof["quote_matches"]:
            states.add("unverified")
            reasons.add("quote_mismatch")
        if source["historical"]:
            states.add("historical")
            reasons.add("historical_evidence")
        if (
            source.get("coverage", "complete") != "complete"
            or source.get("missing")
            or (fresh["reason"] in ("item_incomplete", "resource_incomplete", "missing_or_unknown"))
        ):
            states.add("incomplete")
            reasons.add("incomplete_evidence")
        if not fresh["usable"]:
            states.add("stale")
            reasons.add("evidence_not_current")
    state = next(
        (s for s in ("unverified", "historical", "incomplete", "stale") if s in states), "current"
    )
    return dict(evaluated_at=now, state=state, reasons=sorted(reasons))
