"""Persisted one-course model decisions, using the existing Store and Canvas readers.

Calls are reserved before inference. An expired/failed inference is held, never
blindly retried; this is a call ceiling, not authorization for paid activation.
Offers are private pending intents, not authorized WhatsApp deliveries.
"""

import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from contracts.canvas_sync import course_id as validate_course
from contracts.course_supervision import CourseDecision
from shared.academic_reads import student_json
from shared.canvas_reads import SourceRefreshRequired, _uuid
from shared.course_preparation import preparation_projection, preparation_record
from shared.freshness import legacy_freshness


class CourseSupervisionStore:
    def _supervision_scope(self, conn, user, supervision=None, *, connection_id=None, course=None):
        agent = conn.execute(
            "SELECT * FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user,)
        ).fetchone()
        if not agent:
            raise LookupError("Not found")
        if supervision is not None:
            row = conn.execute(
                "SELECT * FROM wrytely_agent.course_supervisions WHERE agent_id=%s AND id=%s "
                "FOR UPDATE",
                (agent["id"], _uuid(supervision)),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            connection_id, course = row["connection_id"], row["course_id"]
        else:
            row = None
        connection = self._read_connection(conn, agent["id"], _uuid(connection_id))
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if (
            agent["paused"]
            or connection["provider"] != "canvas_extension"
            or connection["state"] != "connected"
            or connection["credential_expires_at"] <= now
            or connection["origin"] not in self._canvas_origins
            or course not in self._courses(conn, connection)
            or not connection["resource_kinds"]
            or (
                row
                and (row["generation"], row["scope_revision"])
                != (connection["generation"], connection["scope_revision"])
            )
        ):
            raise SourceRefreshRequired()
        return agent, connection, row

    def enable_course_supervision(self, verified_user, connection_id, course_id, *, call_limit=6):
        """Explicit session-owned opt-in; replay never refills an exhausted allowance."""
        course = validate_course(course_id)
        if type(call_limit) is not int or not 1 <= call_limit <= 20:
            raise ValueError("Invalid call limit")
        with self.connection() as conn:
            agent, connection, _ = self._supervision_scope(
                conn, verified_user, connection_id=connection_id, course=course
            )
            return conn.execute(
                "INSERT INTO wrytely_agent.course_supervisions "
                "(id,agent_id,connection_id,course_id,generation,scope_revision,call_limit) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(agent_id,connection_id,course_id) "
                "DO UPDATE SET course_id=excluded.course_id RETURNING *",
                (
                    uuid4(),
                    agent["id"],
                    connection["id"],
                    course,
                    connection["generation"],
                    connection["scope_revision"],
                    call_limit,
                ),
            ).fetchone()

    def pause_course_supervision(self, verified_user, supervision_id):
        # Pause must remain possible after disconnect, expiry or scope change.
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            row = conn.execute(
                "UPDATE wrytely_agent.course_supervisions SET state='paused',lease_token=NULL,"
                "lease_until=NULL WHERE agent_id=%s AND id=%s RETURNING id,state",
                (agent, _uuid(supervision_id)),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            return row

    def _supervision_snapshot(self, conn, agent, connection, course):
        rows = self._evidence_rows(
            conn, agent, connection, None, course=course, limit=201, body=True
        )
        if len(rows) > 200:
            raise ValueError("course_supervision_catalog_limit")
        sources = []
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        for row in rows:
            source, selected, state = self._evidence_projection(conn, connection, row)
            if not selected or source["historical"]:
                # Retention does not authorize model disclosure after scope or
                # identity-generation changes. Exclude before private fields enter context.
                continue
            fields = row["private_payload"]["fields"]
            source["fields"] = fields.get("object_fields", fields)
            source["missing"] = list(row["private_payload"]["missing"])
            # Reading original partial text to discover its gaps is not authority
            # to offer/perform work. Keep original coverage/freshness unchanged.
            source["inspection_ready"] = bool(
                selected
                and state == "connected"
                and not source["historical"]
                and not source["missing_pending_confirmation"]
                and source["coverage"] in ("complete", "partial")
                and source["resource_coverage"] in ("complete", "partial", "open")
                and max(row["observed_at"], row["received_at"]) <= now + timedelta(minutes=5)
                and legacy_freshness(min(row["observed_at"], row["received_at"]), now=now).usable
            )
            sources.append(source)
        if len(json.dumps(student_json(sources)).encode()) > 200000:
            raise ValueError("course_supervision_context_limit")
        # Ignore refreshed observation timestamps; immutable content versions drive change.
        digest = hashlib.sha256(
            json.dumps(
                sorted(
                    (
                        str(s["object_id"]),
                        str(s["document_version_id"] or s["latest_version_id"]),
                        # Partial inline originals may have no published version.
                        # Their observation must still fence changed preparation text.
                        str(s["latest_observation_id"]) if not s["freshness"]["usable"] else "",
                    )
                    for s in sources
                )
            ).encode()
        ).hexdigest()
        return student_json(sources), digest

    def claim_course_supervision(self, verified_user, supervision_id):
        with self.connection() as conn:
            agent, connection, row = self._supervision_scope(conn, verified_user, supervision_id)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["state"] == "running" and row["lease_until"] <= now:
                conn.execute(
                    "UPDATE wrytely_agent.course_supervisions SET state='blocked',"
                    "reason='inference_outcome_unknown' WHERE id=%s",
                    (row["id"],),
                )
                return None
            latest_event = conn.execute(
                "SELECT max(e.created_at) AS at FROM wrytely_agent.canvas_evidence_events e "
                "JOIN wrytely_agent.canvas_evidence_objects o ON o.id=e.object_id "
                "AND o.agent_id=e.agent_id JOIN wrytely_agent.canvas_evidence_observations n "
                "ON n.id=e.observation_id AND n.agent_id=e.agent_id WHERE e.agent_id=%s "
                "AND o.connection_id=%s AND o.course_id=%s AND n.generation=%s",
                (agent["id"], connection["id"], row["course_id"], connection["generation"]),
            ).fetchone()["at"]
            changed = latest_event is not None and (
                row["last_source_event_at"] is None or latest_event > row["last_source_event_at"]
            )
            if row["state"] != "ready" or (row["next_check_at"] > now and not changed):
                return None
            if row["calls_reserved"] >= row["call_limit"]:
                conn.execute(
                    "UPDATE wrytely_agent.course_supervisions SET state='blocked',"
                    "reason='call_limit' WHERE id=%s",
                    (row["id"],),
                )
                return None
            sources, digest = self._supervision_snapshot(
                conn, agent["id"], connection, row["course_id"]
            )
            inspections = row["inspections"] if digest == row["snapshot_digest"] else {}
            conn.execute(
                "UPDATE wrytely_agent.course_offers SET state='stale' WHERE supervision_id=%s "
                "AND state='pending' AND NOT EXISTS (SELECT 1 FROM "
                "wrytely_agent.canvas_evidence_objects o JOIN "
                "wrytely_agent.canvas_evidence_observations n ON n.id=o.latest_observation_id "
                "LEFT JOIN wrytely_agent.canvas_document_bindings b ON b.observation_id=n.id "
                "AND b.agent_id=o.agent_id WHERE o.id=course_offers.object_id "
                "AND coalesce(b.document_version_id,n.version_id)=course_offers.version_id)",
                (row["id"],),
            )
            token = uuid4()
            conn.execute(
                "UPDATE wrytely_agent.course_supervisions SET state='running',lease_token=%s,"
                "lease_until=clock_timestamp()+interval '5 minutes',"
                "calls_reserved=calls_reserved+1,"
                "snapshot_digest=%s,inspections=%s,last_source_event_at=%s WHERE id=%s",
                (token, digest, Jsonb(inspections), latest_event, row["id"]),
            )
            offers = conn.execute(
                "SELECT object_id,version_id,state FROM wrytely_agent.course_offers "
                "WHERE supervision_id=%s ORDER BY created_at DESC LIMIT 20",
                (row["id"],),
            ).fetchall()
            return dict(
                id=row["id"],
                token=token,
                course_id=row["course_id"],
                sources=sources,
                inspections=inspections,
                offers=student_json(offers),
                preparations=[
                    {k: p[k] for k in ("key", "object_id", "evidence")} for p in row["preparations"]
                ],
                last_decision=row["last_decision"] if digest == row["snapshot_digest"] else None,
                snapshot_digest=digest,
            )

    def finish_course_supervision(self, verified_user, claim, decision, inspection=None):
        decision = CourseDecision.model_validate(decision)
        with self.connection() as conn:
            agent, connection, row = self._supervision_scope(conn, verified_user, claim["id"])
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                row["state"] != "running"
                or row["lease_token"] != claim["token"]
                or row["lease_until"] <= now
            ):
                raise SourceRefreshRequired()
            sources, digest = self._supervision_snapshot(
                conn, agent["id"], connection, row["course_id"]
            )
            if digest != claim["snapshot_digest"]:
                raise SourceRefreshRequired()
            inspections = row["inspections"]
            preparations = row["preparations"]
            if decision.action != "wait":
                source = next((s for s in sources if s["object_id"] == decision.object_id), None)
                if not source or source["historical"]:
                    raise SourceRefreshRequired()
                if decision.action == "inspect":
                    if not source["inspection_ready"]:
                        raise SourceRefreshRequired()
                    if not inspection or str(inspection["object_id"]) != decision.object_id:
                        raise ValueError("Missing inspection")
                    inspections[decision.object_id] = student_json(inspection)
                    if len(json.dumps(inspections).encode()) > 100000:
                        raise ValueError("Inspection context limit")
                elif decision.action == "prepare":
                    record = preparation_record(decision, sources, inspections)
                    if not any(p["key"] == record["key"] for p in preparations):
                        if len(preparations) >= 20:
                            raise ValueError("Preparation history limit")
                        preparations = [
                            *preparations,
                            {**record, "id": str(uuid4()), "created_at": now.isoformat()},
                        ]
                else:
                    if not source["freshness"]["usable"]:
                        raise SourceRefreshRequired()
                    if source["kind"] != "assignment" or decision.object_id not in inspections:
                        raise ValueError("Offer requires inspected assignment")
                    evidence = [
                        {
                            "object_id": s["object_id"],
                            "version_id": s["document_version_id"] or s["latest_version_id"],
                        }
                        for s in sources
                        if s["object_id"] in inspections
                        and s["freshness"]["usable"]
                        and not s["historical"]
                    ]
                    if len(evidence) > 8:
                        raise ValueError("Offer evidence scope limit")
                    conn.execute(
                        "INSERT INTO wrytely_agent.course_offers "
                        "(id,agent_id,supervision_id,object_id,version_id,evidence,message,reason) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT "
                        "(supervision_id,object_id,version_id) DO NOTHING",
                        (
                            uuid4(),
                            agent["id"],
                            row["id"],
                            _uuid(decision.object_id),
                            _uuid(source["document_version_id"] or source["latest_version_id"]),
                            Jsonb(evidence),
                            decision.message,
                            decision.reason,
                        ),
                    )
            return conn.execute(
                "UPDATE wrytely_agent.course_supervisions SET state='ready',lease_token=NULL,"
                "lease_until=NULL,inspections=%s,preparations=%s,last_decision=%s,reason=NULL,"
                "next_check_at=clock_timestamp()+(%s * interval '1 second') WHERE id=%s "
                "RETURNING id,state,next_check_at,calls_reserved,call_limit",
                (
                    Jsonb(inspections),
                    Jsonb(preparations),
                    Jsonb(decision.model_dump()),
                    0 if decision.action == "inspect" else decision.next_check_seconds,
                    row["id"],
                ),
            ).fetchone()

    def hold_course_supervision(self, verified_user, claim, *, reason="episode_failed_or_unknown"):
        if reason not in {
            "episode_failed_or_unknown",
            "model_provider_unavailable",
            "model_rate_limited",
            "model_access_denied",
            "model_not_found",
            "model_response_incomplete",
            "model_request_failed",
        }:
            raise ValueError("Invalid supervision hold reason")
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            conn.execute(
                "UPDATE wrytely_agent.course_supervisions SET state='blocked',"
                "reason=%s,lease_token=NULL,lease_until=NULL "
                "WHERE agent_id=%s AND id=%s AND lease_token=%s AND state='running'",
                (reason, agent, claim["id"], claim["token"]),
            )

    def course_supervision_status(self, verified_user, supervision_id):
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            row = conn.execute(
                "SELECT id,state,next_check_at,calls_reserved,call_limit,last_decision,reason, "
                "notification_consent,connection_id,course_id,generation,scope_revision,"
                "preparations "
                "FROM wrytely_agent.course_supervisions WHERE agent_id=%s AND id=%s",
                (agent, _uuid(supervision_id)),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            connection = self._read_connection(conn, agent, row.pop("connection_id"))
            course = row.pop("course_id")
            scope_current = (row.pop("generation"), row.pop("scope_revision")) == (
                connection["generation"],
                connection["scope_revision"],
            )
            sources = []
            if row["preparations"]:
                sources, _ = self._supervision_snapshot(conn, agent, connection, course)
            owner = conn.execute(
                "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (agent,)
            ).fetchone()
            row["preparations"] = preparation_projection(
                row["preparations"],
                sources,
                active=scope_current and not owner["paused"] and row["state"] != "paused",
            )
            row["offers"] = conn.execute(
                "SELECT id,object_id,version_id,message,reason,state "
                "FROM wrytely_agent.course_offers "
                "WHERE agent_id=%s AND supervision_id=%s ORDER BY created_at DESC LIMIT 20",
                (agent, row["id"]),
            ).fetchall()
            return row

    def find_course_supervision(self, verified_user, connection_id, course_id):
        """Session-owned lookup only; never enroll, resume or refill on page reload."""
        course = validate_course(course_id)
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            connection = self._read_connection(conn, agent, _uuid(connection_id))
            row = conn.execute(
                "SELECT id FROM wrytely_agent.course_supervisions "
                "WHERE agent_id=%s AND connection_id=%s AND course_id=%s",
                (agent, connection["id"], course),
            ).fetchone()
        # Release the first transaction's agent lock before the original private read.
        return self.course_supervision_status(verified_user, row["id"]) if row else None

    def decide_course_offer(self, verified_user, supervision_id, offer_id, *, accept):
        """Persist explicit student decision; return existing draft API arguments.

        Trusted HTTP assembly calls create_canvas_draft_responsibility with this
        spec after acceptance. Its stable key deduplicates crashes/repeated replies;
        it independently rechecks source authorization. No delivery consent implied.
        """
        if type(accept) is not bool:
            raise ValueError("Explicit decision required")
        with self.connection() as conn:
            agent, connection, row = self._supervision_scope(conn, verified_user, supervision_id)
            if row["state"] == "paused":
                raise SourceRefreshRequired()
            offer = conn.execute(
                "SELECT * FROM wrytely_agent.course_offers WHERE agent_id=%s "
                "AND supervision_id=%s AND id=%s FOR UPDATE",
                (agent["id"], row["id"], _uuid(offer_id)),
            ).fetchone()
            if not offer:
                raise LookupError("Not found")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if offer["state"] == "pending" and now >= offer["created_at"] + timedelta(hours=24):
                raise ValueError("Offer expired")
            sources, _ = self._supervision_snapshot(conn, agent["id"], connection, row["course_id"])
            source = next((s for s in sources if s["object_id"] == str(offer["object_id"])), None)
            if (
                not source
                or not source["freshness"]["usable"]
                or str(source["document_version_id"] or source["latest_version_id"])
                != str(offer["version_id"])
            ):
                raise SourceRefreshRequired()
            for pin in offer["evidence"]:
                current = next((s for s in sources if s["object_id"] == pin["object_id"]), None)
                if (
                    not current
                    or not current["freshness"]["usable"]
                    or str(current["document_version_id"] or current["latest_version_id"])
                    != pin["version_id"]
                ):
                    raise SourceRefreshRequired()
            target = "accepted" if accept else "declined"
            if offer["state"] not in ("pending", target):
                raise ValueError("Offer decision already recorded or stale")
            conn.execute(
                "UPDATE wrytely_agent.course_offers SET state=%s WHERE id=%s",
                (target, offer["id"]),
            )
            return {
                "state": target,
                "draft_request": {
                    "objective": offer["message"],
                    "request_key": "course-offer:" + str(offer["id"]),
                    "object_ids": [pin["object_id"] for pin in offer["evidence"]],
                }
                if accept
                else None,
            }

    def due_course_supervisions(self, *, limit=20):
        """Internal service discovery only; never expose the returned user IDs as an RPC."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid due limit")
        with self.connection() as conn:
            return conn.execute(
                "SELECT s.id,a.user_id FROM wrytely_agent.course_supervisions s "
                "JOIN wrytely_agent.agents a ON a.id=s.agent_id WHERE NOT a.paused AND "
                "((s.state='ready' AND (s.next_check_at<=now() OR EXISTS ("
                "SELECT 1 FROM wrytely_agent.canvas_evidence_events e JOIN "
                "wrytely_agent.canvas_evidence_objects o ON o.id=e.object_id "
                "AND o.agent_id=e.agent_id "
                "JOIN wrytely_agent.canvas_evidence_observations n ON n.id=e.observation_id "
                "AND n.agent_id=e.agent_id WHERE e.agent_id=s.agent_id "
                "AND o.connection_id=s.connection_id AND o.course_id=s.course_id "
                "AND n.generation=s.generation AND (s.last_source_event_at IS NULL "
                "OR e.created_at>s.last_source_event_at)))) OR "
                "(s.state='running' AND s.lease_until<=now())) "
                "ORDER BY s.next_check_at,s.id LIMIT %s",
                (limit,),
            ).fetchall()

    def reschedule_course_source_change(self, verified_user, claim):
        """Only known source races retry; changed authority, pause and unknown inference do not."""
        try:
            with self.connection() as conn:
                _, _, row = self._supervision_scope(conn, verified_user, claim["id"])
                now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
                if (
                    row["state"] != "running"
                    or row["lease_token"] != claim["token"]
                    or row["lease_until"] <= now
                ):
                    return False
                conn.execute(
                    "UPDATE wrytely_agent.course_supervisions SET state='ready',"
                    "next_check_at=clock_timestamp(),lease_token=NULL,lease_until=NULL,"
                    "inspections='{}',reason='source_changed_during_decision' WHERE id=%s",
                    (row["id"],),
                )
                return True
        except SourceRefreshRequired:
            return False
