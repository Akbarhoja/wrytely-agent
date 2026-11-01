"""Private begin/part staging only; finish, publication and cleanup remain separate."""

import hashlib
import json
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from contracts.canvas_sync import replay_key
from shared.canvas_document_wire import (
    _keys,
    validate_canvas_document,
    validate_canvas_document_header,
)
from shared.canvas_sync import CanvasSyncConflict, _hash
from shared.document_sections import DocumentSection

_COMMON = {
    "schema_version",
    "operation",
    "connection_id",
    "generation",
    "scan_id",
    "subject",
    "lease_token",
    "request_key",
}
_BEGIN = {"resource", "owner_object", "object_fields", "metadata", "manifest"}


class CanvasDocumentUploadLimited(ValueError):
    """Controlled quota error; assembly may map to429 with a bounded retry hint."""


def _request(body, operation):
    _keys(
        body,
        _COMMON
        | (
            _BEGIN
            if operation == "begin_document"
            else {"upload_id"}
            if operation == "finish_document"
            else {"upload_id", "parts"}
        ),
    )
    if (
        type(body["schema_version"]) is not int
        or body["schema_version"] != 2
        or body["operation"] != operation
    ):
        raise ValueError("Invalid document discriminator")
    if type(body["generation"]) is not int or body["generation"] < 1:
        raise ValueError("Invalid document generation")
    for name in ("connection_id", "scan_id", "lease_token"):
        if not isinstance(body[name], str) or str(UUID(body[name])) != body[name]:
            raise ValueError("Invalid document context ID")
    if not isinstance(body["subject"], str) or not 1 <= len(body["subject"]) <= 1024:
        raise ValueError("Invalid document subject")
    replay_key(body["request_key"])
    try:
        if len(json.dumps(body, ensure_ascii=False, allow_nan=False).encode()) > 1024 * 1024:
            raise ValueError("Document request size limit")
    except (UnicodeError, TypeError):
        raise ValueError("Invalid document request") from None
    # Authorization is deliberately outside immutable replay identity.
    return _hash({k: v for k, v in body.items() if k != "lease_token"})


class CanvasDocumentUploadStore:
    def _document_context(self, conn, actor, body):
        row, scan = self._scan(conn, actor, body["scan_id"], body["generation"])
        if str(row["id"]) != body["connection_id"] or row["provider_subject"] != body["subject"]:
            raise CanvasSyncConflict("subject_changed")
        self._live(conn, scan, body["lease_token"])
        return row, scan

    def _document_upload(self, conn, row, scan, upload_id):
        upload = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_document_uploads WHERE id=%s AND agent_id=%s "
            "AND connection_id=%s AND scan_id=%s AND generation=%s FOR UPDATE",
            (upload_id, row["agent_id"], row["id"], scan["id"], row["generation"]),
        ).fetchone()
        if not upload:
            raise LookupError("Not found")
        if not conn.execute(
            "SELECT 1 WHERE %s>clock_timestamp()", (upload["expires_at"],)
        ).fetchone():
            raise CanvasSyncConflict("document_expired")
        resource = conn.execute(
            "SELECT coverage FROM wrytely_agent.canvas_resources WHERE scan_id=%s AND "
            "resource_key=%s",
            (scan["id"], upload["resource_key"]),
        ).fetchone()
        if not resource or resource["coverage"] != "open":
            raise CanvasSyncConflict("resource_terminal")
        return upload

    def _document_receipt(self, conn, actor, row, scan, body, digest):
        receipt = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_document_upload_receipts WHERE "
            "scan_id=%s AND operation=%s AND request_key=%s",
            (scan["id"], body["operation"], body["request_key"]),
        ).fetchone()
        if receipt:
            if digest != receipt["digest"]:
                raise CanvasSyncConflict("document_conflict")
            self._document_context(conn, actor, body)
            self._document_upload(conn, row, scan, receipt["upload_id"])
            return {**receipt["response"], "replayed": True}

    def _save_document_receipt(self, conn, actor, row, scan, body, digest, upload_id):
        # Fresh authorization/expiry at final commit; agent/connection lock is
        # retained throughout, serializing controls and competing quota writers.
        self._document_context(conn, actor, body)
        upload = self._document_upload(conn, row, scan, upload_id)
        slots = conn.execute(
            "SELECT slot FROM wrytely_agent.canvas_document_upload_parts WHERE "
            "upload_id=%s ORDER BY slot",
            (upload_id,),
        ).fetchall()
        result = {
            "schema_version": 2,
            "operation": body["operation"],
            "receipt_id": str(uuid4()),
            "upload_id": str(upload_id),
            "expires_at": upload["expires_at"].isoformat(),
            "received_slots": [r["slot"] for r in slots],
            "replayed": False,
        }
        if body["operation"] == "finish_document":
            root = conn.execute(
                "SELECT protocol_payload FROM wrytely_agent.canvas_document_versions WHERE id=%s "
                "AND agent_id=%s AND object_id=%s",
                (upload["document_version_id"], row["agent_id"], upload["object_id"]),
            ).fetchone()
            if root is None or root["protocol_payload"] is None:
                raise CanvasSyncConflict("document_not_ready")
            from contracts.source_digest import source_digest

            del result["received_slots"]
            result.update(
                document_version_id=str(upload["document_version_id"]),
                document_digest=source_digest(root["protocol_payload"]),
                ready=True,
            )
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_document_upload_receipts VALUES (%s,%s,%s,%s,%s,%s)",
            (scan["id"], body["operation"], body["request_key"], upload_id, digest, Jsonb(result)),
        )
        return result

    def begin_document_upload(self, actor, body, *, extractor_versions):
        digest = _request(body, "begin_document")
        header = validate_canvas_document_header(
            **{k: body[k] for k in _BEGIN}, extractor_versions=extractor_versions
        )
        with self.connection() as conn:
            row, scan = self._document_context(conn, actor, body)
            replay = self._document_receipt(conn, actor, row, scan, body, digest)
            if replay:
                return replay
            key = header["resource"]["course_id"] + "/" + header["resource"]["kind"]
            resource = conn.execute(
                "SELECT coverage FROM wrytely_agent.canvas_resources WHERE scan_id=%s AND "
                "resource_key=%s",
                (scan["id"], key),
            ).fetchone()
            if not resource:
                raise CanvasSyncConflict("resource_not_selected")
            if resource["coverage"] != "open":
                raise CanvasSyncConflict("resource_terminal")
            count = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_uploads WHERE "
                "connection_id=%s "
                "AND expires_at>clock_timestamp()",
                (row["id"],),
            ).fetchone()["n"]
            if count >= 4:
                raise CanvasDocumentUploadLimited("document_upload_limit")
            upload = conn.execute(
                "INSERT INTO wrytely_agent.canvas_document_uploads "
                "(id,agent_id,connection_id,scan_id,generation,resource_key,header,expires_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,LEAST(%s,clock_timestamp()+interval '30 "
                "minutes')) RETURNING id",
                (
                    uuid4(),
                    row["agent_id"],
                    row["id"],
                    scan["id"],
                    row["generation"],
                    key,
                    Jsonb(header),
                    scan["expires_at"],
                ),
            ).fetchone()
            return self._save_document_receipt(conn, actor, row, scan, body, digest, upload["id"])

    def put_document_parts(self, actor, body):
        digest = _request(body, "put_document_parts")
        if (
            not isinstance(body["upload_id"], str)
            or str(UUID(body["upload_id"])) != body["upload_id"]
        ):
            raise ValueError("Invalid upload ID")
        parts = body["parts"]
        if type(parts) is not list or not 1 <= len(parts) <= 50:
            raise ValueError("Document part count limit")
        seen = set()
        for part in parts:
            _keys(part, ("slot", "text"))
            if type(part["slot"]) is not int or not 0 <= part["slot"] < 512 or part["slot"] in seen:
                raise ValueError("Invalid document slot")
            seen.add(part["slot"])
        with self.connection() as conn:
            row, scan = self._document_context(conn, actor, body)
            replay = self._document_receipt(conn, actor, row, scan, body, digest)
            if replay:
                return replay
            upload = self._document_upload(conn, row, scan, UUID(body["upload_id"]))
            manifest = upload["header"]["manifest"]
            additions = []
            for part in parts:
                if part["slot"] >= len(manifest):
                    raise ValueError("Undeclared document slot")
                slot = manifest[part["slot"]]
                prior = conn.execute(
                    "SELECT text FROM wrytely_agent.canvas_document_upload_parts WHERE "
                    "upload_id=%s AND slot=%s",
                    (upload["id"], part["slot"]),
                ).fetchone()
                if prior:
                    if prior["text"] != part["text"]:
                        raise CanvasSyncConflict("document_conflict")
                    continue
                DocumentSection(**slot, text=part["text"])
                additions.append(part)
            used = conn.execute(
                "SELECT COALESCE(sum(octet_length(p.text)),0) AS n FROM "
                "wrytely_agent.canvas_document_upload_parts p "
                "JOIN wrytely_agent.canvas_document_uploads u ON u.id=p.upload_id WHERE "
                "u.connection_id=%s",
                (row["id"],),
            ).fetchone()["n"]
            if used + sum(len(p["text"].encode()) for p in additions) > 8 * 1024 * 1024:
                raise CanvasDocumentUploadLimited("document_bytes_limit")
            for part in additions:
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_document_upload_parts VALUES (%s,%s,%s)",
                    (upload["id"], part["slot"], part["text"]),
                )
            return self._save_document_receipt(conn, actor, row, scan, body, digest, upload["id"])

    def finish_document_upload(self, actor, body, *, extractor_versions):
        digest = _request(body, "finish_document")
        if (
            not isinstance(body["upload_id"], str)
            or str(UUID(body["upload_id"])) != body["upload_id"]
        ):
            raise ValueError("Invalid upload ID")
        with self.connection() as conn:
            row, scan = self._document_context(conn, actor, body)
            replay = self._document_receipt(conn, actor, row, scan, body, digest)
            if replay:
                return replay
            upload = self._document_upload(conn, row, scan, UUID(body["upload_id"]))
            parts = conn.execute(
                "SELECT slot,text FROM wrytely_agent.canvas_document_upload_parts "
                "WHERE upload_id=%s ORDER BY slot",
                (upload["id"],),
            ).fetchall()
            root = validate_canvas_document(
                **upload["header"], parts=parts, extractor_versions=extractor_versions
            )
            # Shell identity only: readers require an actual observation and binding.
            obj = conn.execute(
                "INSERT INTO wrytely_agent.canvas_evidence_objects "
                "(id,agent_id,connection_id,subject_digest,course_id,kind,provider_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(connection_id,subject_digest,course_id,kind,provider_id) "
                "DO UPDATE SET provider_id=excluded.provider_id RETURNING id",
                (
                    uuid4(),
                    row["agent_id"],
                    row["id"],
                    hashlib.sha256(row["provider_subject"].encode()).hexdigest(),
                    root.course_id,
                    root.owner_kind,
                    root.provider_id,
                ),
            ).fetchone()
            version_id = self._stage_canvas_document_sections(
                conn,
                row["agent_id"],
                obj["id"],
                root.sections,
                format=root.payload["fields"]["format"],
                extractor_version=root.payload["fields"]["extractor_version"],
                protocol_payload=root.payload,
            )
            if (
                upload["document_version_id"] is not None
                and upload["document_version_id"] != version_id
            ):
                raise CanvasSyncConflict("document_conflict")
            conn.execute(
                "UPDATE wrytely_agent.canvas_document_uploads SET "
                "object_id=%s,document_version_id=%s "
                "WHERE id=%s",
                (obj["id"], version_id, upload["id"]),
            )
            return self._save_document_receipt(conn, actor, row, scan, body, digest, upload["id"])
