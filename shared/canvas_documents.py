"""Internal transactional section storage and pinned private reads.

No upload wire, canonical protocol root digest, source promotion or model consumer.
Private writer helpers must run inside a trusted, already-authorized transaction.
"""

import json
import re
from dataclasses import asdict
from uuid import uuid4

from psycopg.types.json import Jsonb

from contracts.source_digest import canonical_source_bytes, source_digest
from shared.canvas_reads import SourceRefreshRequired, _bound, _uuid
from shared.canvas_sync import CanvasSyncConflict, _hash
from shared.document_sections import (
    DocumentSections,
    page_document_sections,
    validate_document_sections,
)


def _section_manifest(document):
    return [
        {key: value for key, value in asdict(s).items() if key != "text"} for s in document.sections
    ]


def _fingerprint(document, format, extractor_version, protocol_payload=None):
    data = {
        "format": format,
        "extractor_version": extractor_version,
        "total_characters": document.total_characters,
        "total_pages": document.total_pages,
        "manifest": _section_manifest(document),
    }
    if protocol_payload is not None:
        # New protocol roots distinguish changed academic fields from body-only
        # legacy section storage, without changing old internal fingerprints.
        payload = json.loads(canonical_source_bytes(protocol_payload))
        fields = payload["fields"]
        if (
            payload["kind"] != "document"
            or payload["content"] != ""
            or set(fields)
            != {
                "format",
                "extractor_version",
                "total_pages",
                "total_characters",
                "slots",
                "owner_kind",
                "object_fields",
            }
            or any(
                fields[k] != data[k]
                for k in ("format", "extractor_version", "total_characters", "total_pages")
            )
            or fields["slots"] != data["manifest"]
        ):
            raise ValueError("Protocol root/sections mismatch")
        data["protocol_digest"] = source_digest(payload)
    return _hash(data)


def _validate_format(document, format, extractor_version):
    if (
        not isinstance(format, str)
        or format not in {"text", "html_text", "pdf_text"}
        or not isinstance(extractor_version, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", extractor_version)
        or (format == "pdf_text") != (document.total_pages is not None)
    ):
        raise ValueError("Invalid document storage metadata")


class CanvasDocumentStore:
    def _stage_canvas_document_sections(
        self,
        conn,
        agent_id,
        object_id,
        document,
        *,
        format,
        extractor_version,
        protocol_payload=None,
    ):
        """Trusted internal write, not a user/model/ingestion endpoint. Does not bind or publish."""
        if not isinstance(document, DocumentSections):
            raise ValueError("Validated document sections required")
        document = DocumentSections(
            document.sections, document.total_characters, document.total_pages
        )
        _validate_format(document, format, extractor_version)
        agent_id, object_id = _uuid(agent_id), _uuid(object_id)
        agent = conn.execute(
            "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE", (agent_id,)
        ).fetchone()
        obj = conn.execute(
            "SELECT id,kind FROM wrytely_agent.canvas_evidence_objects WHERE agent_id=%s AND "
            "id=%s FOR UPDATE",
            (agent_id, object_id),
        ).fetchone()
        if not agent or not obj:
            raise LookupError("Not found")
        fingerprint = _fingerprint(document, format, extractor_version, protocol_payload)
        if protocol_payload is not None and protocol_payload["fields"]["owner_kind"] != obj["kind"]:
            raise ValueError("Protocol owner kind mismatch")
        row = conn.execute(
            "INSERT INTO wrytely_agent.canvas_document_versions (id,agent_id,object_id,"
            "section_fingerprint,format,extractor_version,total_characters,total_pages,"
            "manifest,protocol_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON "
            "CONFLICT(agent_id,"
            "object_id,section_fingerprint) DO NOTHING RETURNING id",
            (
                uuid4(),
                agent_id,
                object_id,
                fingerprint,
                format,
                extractor_version,
                document.total_characters,
                document.total_pages,
                Jsonb(_section_manifest(document)),
                Jsonb(protocol_payload) if protocol_payload is not None else None,
            ),
        ).fetchone()
        if row is None:
            return conn.execute(
                "SELECT id FROM wrytely_agent.canvas_document_versions WHERE agent_id=%s AND "
                "object_id=%s AND section_fingerprint=%s",
                (agent_id, object_id, fingerprint),
            ).fetchone()["id"]
        for section in document.sections:
            conn.execute(
                "INSERT INTO wrytely_agent.canvas_document_sections (id,agent_id,object_id,"
                "document_version_id,slot,start_offset,end_offset,page,text,text_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    agent_id,
                    object_id,
                    row["id"],
                    section.slot,
                    section.start,
                    section.end,
                    section.page,
                    section.text,
                    section.text_sha256,
                ),
            )
        return row["id"]

    @staticmethod
    def _load_canvas_document(conn, agent_id, object_id, version_id):
        root = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_document_versions WHERE agent_id=%s AND "
            "object_id=%s AND id=%s",
            (agent_id, object_id, version_id),
        ).fetchone()
        if not root:
            raise LookupError("Not found")
        sections = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_document_sections WHERE agent_id=%s AND "
            "object_id=%s AND document_version_id=%s ORDER BY slot",
            (agent_id, object_id, version_id),
        ).fetchall()
        document = validate_document_sections(
            root["manifest"],
            [{"slot": s["slot"], "text": s["text"]} for s in sections],
            total_characters=root["total_characters"],
            total_pages=root["total_pages"],
        )
        _validate_format(document, root["format"], root["extractor_version"])
        # Both manifest and per-row provenance/hashes must agree, not only body length.
        for actual, expected in zip(sections, document.sections, strict=True):
            if (
                actual["start_offset"],
                actual["end_offset"],
                actual["page"],
                actual["text_sha256"],
            ) != (expected.start, expected.end, expected.page, expected.text_sha256):
                raise ValueError("Stored document section mismatch")
        if (
            _fingerprint(
                document, root["format"], root["extractor_version"], root["protocol_payload"]
            )
            != root["section_fingerprint"]
        ):
            raise ValueError("Stored document integrity mismatch")
        return document, sections

    def _document_observation(
        self, conn, agent, duty, object_id, observation_id, *, task=False, purpose="inspect"
    ):
        owned = conn.execute(
            "SELECT connection_id FROM wrytely_agent.canvas_evidence_objects WHERE id=%s "
            "AND agent_id=%s",
            (object_id, agent),
        ).fetchone()
        if not owned:
            raise LookupError("Not found")
        connection = self._read_connection(conn, agent, owned["connection_id"])
        rows = self._evidence_rows(
            conn,
            agent,
            connection,
            duty,
            task=task,
            object_id=object_id,
            observation_id=observation_id,
            body=True,
        )
        if not rows:
            raise LookupError("Not found")
        row = rows[0]
        projection, selected, state = self._evidence_projection(
            conn, connection, row, purpose=purpose
        )
        if (
            state != "connected"
            or not selected
            or row["observation_generation"] != connection["generation"]
        ):
            raise SourceRefreshRequired()
        return connection, row, projection

    def _bind_canvas_document_sections(self, conn, agent_id, object_id, observation_id, version_id):
        """Internal binding; future C2 publisher must supply its live scan fence."""
        agent_id, object_id = _uuid(agent_id), _uuid(object_id)
        observation_id, version_id = _uuid(observation_id), _uuid(version_id)
        if not conn.execute(
            "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE", (agent_id,)
        ).fetchone():
            raise LookupError("Not found")
        connection, row, _ = self._document_observation(
            conn, agent_id, None, object_id, observation_id
        )
        document, _ = self._load_canvas_document(conn, agent_id, object_id, version_id)
        if (document.unrepresented_pages or not document.total_characters) and (
            row["item_coverage"] == "complete" or not row["private_payload"]["missing"]
        ):
            raise ValueError("Document gaps require explicit incomplete evidence")
        self._finish_canvas_read(conn, None, {}, connection)
        prior = conn.execute(
            "SELECT document_version_id FROM wrytely_agent.canvas_document_bindings "
            "WHERE observation_id=%s AND agent_id=%s AND object_id=%s",
            (observation_id, agent_id, object_id),
        ).fetchone()
        if prior:
            if prior["document_version_id"] != version_id:
                raise CanvasSyncConflict("document_binding_changed")
            return
        # Do not advance observation age, legacy current pointers, events or resource coverage.
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_document_bindings(observation_id,agent_id,"
            "object_id,document_version_id) VALUES (%s,%s,%s,%s)",
            (observation_id, agent_id, object_id, version_id),
        )

    def _read_canvas_document_sections(
        self, user, lease, object_id, *, observation_id, document_version_id, first_slot=0, limit=10
    ):
        _bound(first_slot, 0, 512)
        _bound(limit, 1, 20)
        object_id, observation_id, version_id = map(
            _uuid, (object_id, observation_id, document_version_id)
        )
        with self.connection() as conn:
            agent, duty = self._read_identity(conn, user, lease)
            connection, row, projection = self._document_observation(
                conn, agent, duty, object_id, observation_id, task=lease is not None
            )
            bound = conn.execute(
                "SELECT 1 FROM wrytely_agent.canvas_document_bindings WHERE agent_id=%s AND "
                "object_id=%s AND observation_id=%s AND document_version_id=%s",
                (agent, object_id, observation_id, version_id),
            ).fetchone()
            if not bound:
                raise LookupError("Not found")
            document, stored = self._load_canvas_document(conn, agent, object_id, version_id)
            page = page_document_sections(document, first_slot=first_slot, limit=limit)
            result = {
                "object_id": object_id,
                "observation_id": observation_id,
                "document_version_id": version_id,
                "sections": [
                    {"segment_id": stored[s.slot]["id"], **asdict(s)} for s in page.sections
                ],
                "next_slot": page.next_slot,
                "total_slots": page.total_slots,
                "coverage": projection["coverage"],
                "missing": row["private_payload"]["missing"],
                "historical": projection["historical"],
                "freshness": projection["freshness"],
            }
            return self._finish_canvas_read(conn, lease, result, connection)

    def read_canvas_document_sections(self, verified_user, object_id, **kwargs):
        return self._read_canvas_document_sections(verified_user, None, object_id, **kwargs)

    def read_canvas_document_sections_for_task(self, lease, object_id, **kwargs):
        return self._read_canvas_document_sections(None, lease, object_id, **kwargs)
