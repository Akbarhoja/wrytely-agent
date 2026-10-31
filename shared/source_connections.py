"""Hash-only Canvas device pairing on the existing Store; no provider or HTTP IO."""

import hashlib
import re
import secrets
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID, uuid4


class PairingRejected(ValueError):
    def __init__(self):
        super().__init__("Invalid pairing")


class PairingLimited(ValueError):
    def __init__(self):
        super().__init__("Pairing rate limited")


class SourceCredentialRejected(PermissionError):
    def __init__(self):
        super().__init__("Source credential rejected")


def canvas_origin(value):
    """Require an exact configured HTTPS origin, without canonicalization surprises."""
    if not isinstance(value, str) or len(value) > 253 or not value.isascii():
        raise ValueError("Invalid Canvas origin")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.netloc != parsed.hostname
        or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", parsed.netloc)
        or value != "https://" + parsed.netloc
    ):
        raise ValueError("Invalid Canvas origin")
    return value


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe(row):
    state = row["state"]
    if state in ("pending_identity", "connected") and row["credential_expires_at"] <= datetime.now(
        UTC
    ):
        state = "reconnect_required"
    return {
        "connection_id": str(row["id"]),
        "provider": row["provider"],
        "origin": row["origin"],
        "state": state,
        "generation": row["generation"],
        "credential_expires_at": row["credential_expires_at"].isoformat(),
    }


class SourceConnectionStore:
    def create_pairing(self, verified_user, allowed_origin):
        """Caller supplies a verified session subject; origin also needs operator allowlisting."""
        origin = canvas_origin(allowed_origin)
        if origin not in self._canvas_origins:
            raise ValueError("Canvas origin not configured")
        code = secrets.token_urlsafe(24)  # 192-bit copyable code; never a guessable six-digit PIN.
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE",
                (verified_user,),
            ).fetchone()
            if not agent:
                raise LookupError("Complete setup first")
            previous = conn.execute(
                "SELECT *,window_started_at>clock_timestamp()-interval '10 minutes' AS recent "
                "FROM wrytely_agent.source_pairings WHERE agent_id=%s",
                (agent["id"],),
            ).fetchone()
            if previous and previous["recent"] and previous["issued_count"] >= 5:
                raise PairingLimited()
            result = conn.execute(
                "INSERT INTO wrytely_agent.source_pairings(agent_id,origin,code_hash,expires_at) "
                "VALUES (%s,%s,%s,clock_timestamp()+interval '10 minutes') "
                "ON CONFLICT(agent_id) DO UPDATE SET origin=excluded.origin, "
                "code_hash=excluded.code_hash,expires_at=excluded.expires_at,consumed_at=NULL, "
                "issued_count=CASE WHEN source_pairings.window_started_at> "
                "clock_timestamp()-interval '10 minutes' THEN source_pairings.issued_count+1 "
                "ELSE 1 END,window_started_at=CASE WHEN source_pairings.window_started_at> "
                "clock_timestamp()-interval '10 minutes' THEN source_pairings.window_started_at "
                "ELSE clock_timestamp() END RETURNING expires_at",
                (agent["id"], origin, _digest(code)),
            ).fetchone()
        return {"challenge": code, "code": code, "expires_at": result["expires_at"].isoformat()}

    @staticmethod
    def _redeem_budget(conn, device_public_id):
        # Bounded global budget first: random device IDs cannot grow unlimited rate rows.
        conn.execute("SELECT pg_advisory_xact_lock(20417352)")
        conn.execute(
            "DELETE FROM wrytely_agent.source_pairing_rates WHERE "
            "window_started_at<=clock_timestamp()-interval '1 minute'"
        )
        for bucket, limit in (("global", 120), ("device:" + _digest(device_public_id), 10)):
            row = conn.execute(
                "INSERT INTO wrytely_agent.source_pairing_rates "
                "(bucket_key,window_started_at,attempts) VALUES (%s,clock_timestamp(),1) "
                "ON CONFLICT(bucket_key) DO UPDATE SET "
                "attempts=least(source_pairing_rates.attempts+1,121) "
                "RETURNING attempts",
                (bucket,),
            ).fetchone()
            if row["attempts"] > limit:
                return False
        return True

    def redeem_pairing(self, code, device_public_id):
        """Possession of a one-use code binds one device; failed attempts commit their budget."""
        if (
            not isinstance(code, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{32}", code)
            or not isinstance(device_public_id, str)
            or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", device_public_id)
        ):
            raise PairingRejected()
        result = None
        limited = False
        with self.connection() as conn:
            if not self._redeem_budget(conn, device_public_id):
                limited = True
            else:
                candidate = conn.execute(
                    "SELECT agent_id FROM wrytely_agent.source_pairings WHERE code_hash=%s",
                    (_digest(code),),
                ).fetchone()
                if candidate:
                    conn.execute(
                        "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE",
                        (candidate["agent_id"],),
                    )
                    pairing = conn.execute(
                        "UPDATE wrytely_agent.source_pairings SET consumed_at=clock_timestamp() "
                        "WHERE agent_id=%s AND code_hash=%s AND consumed_at IS NULL "
                        "AND expires_at>clock_timestamp() RETURNING *",
                        (candidate["agent_id"], _digest(code)),
                    ).fetchone()
                    if pairing and pairing["origin"] in self._canvas_origins:
                        bearer = secrets.token_urlsafe(32)
                        row = conn.execute(
                            "INSERT INTO wrytely_agent.source_connections "
                            "(id,agent_id,origin,device_public_id,state,credential_hash, "
                            "credential_expires_at) VALUES (%s,%s,%s,%s,'pending_identity',%s, "
                            "clock_timestamp()+interval '30 days') "
                            "ON CONFLICT(agent_id,origin,device_public_id) DO UPDATE SET "
                            "generation=source_connections.generation+1,provider_subject=NULL, "
                            "state='pending_identity',credential_hash=excluded.credential_hash, "
                            "credential_expires_at=excluded.credential_expires_at, "
                            "updated_at=clock_timestamp() RETURNING *",
                            (
                                uuid4(),
                                pairing["agent_id"],
                                pairing["origin"],
                                device_public_id,
                                _digest(bearer),
                            ),
                        ).fetchone()
                        if row["generation"] > 1:
                            self._reset_canvas_context(conn, row["id"])
                        result = {**_safe(row), "ingestion_bearer": bearer}
        if limited:
            raise PairingLimited()
        if result is None:
            raise PairingRejected()
        return result

    def _lock_canvas_credential(self, conn, credential, origin):
        """Internal transaction helper: agent lock serializes with revoke, re-pair and sync."""
        if (
            not isinstance(credential, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", credential)
            or not isinstance(origin, str)
            or origin not in self._canvas_origins
        ):
            raise SourceCredentialRejected()
        candidate = conn.execute(
            "SELECT agent_id FROM wrytely_agent.source_connections WHERE credential_hash=%s",
            (_digest(credential),),
        ).fetchone()
        if candidate:
            conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE",
                (candidate["agent_id"],),
            )
            row = conn.execute(
                "SELECT * FROM wrytely_agent.source_connections WHERE agent_id=%s "
                "AND credential_hash=%s AND origin=%s AND credential_expires_at>clock_timestamp() "
                "AND state IN ('pending_identity','connected') FOR UPDATE",
                (candidate["agent_id"], _digest(credential), origin),
            ).fetchone()
            if row:
                return row
        raise SourceCredentialRejected()

    def bind_canvas_identity(self, credential, origin, provider_subject):
        """Provider identity is evidence from M's verified same-session adapter, not user input."""
        if (
            not isinstance(provider_subject, str)
            or not 1 <= len(provider_subject) <= 1024
            or provider_subject.strip() != provider_subject
            or any(ord(char) < 32 for char in provider_subject)
        ):
            raise ValueError("Invalid provider subject")
        changed = False
        with self.connection() as conn:
            row = self._lock_canvas_credential(conn, credential, origin)
            if row["provider_subject"] is not None and row["provider_subject"] != provider_subject:
                conn.execute(
                    "UPDATE wrytely_agent.source_connections SET generation=generation+1, "
                    "state='reconnect_required',credential_hash=NULL,updated_at=clock_timestamp() "
                    "WHERE id=%s",
                    (row["id"],),
                )
                changed = True
                self._reset_canvas_context(conn, row["id"])
            else:
                row = conn.execute(
                    "UPDATE wrytely_agent.source_connections SET provider_subject=%s, "
                    "state='connected',updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                    (provider_subject, row["id"]),
                ).fetchone()
        # Raise after commit: a mismatched login must not roll back its revocation.
        if changed:
            raise SourceCredentialRejected()
        return _safe(row)

    def source_connection(self, verified_user, connection_id):
        try:
            connection_id = UUID(str(connection_id))
        except (ValueError, TypeError, AttributeError):
            return None
        with self.connection() as conn:
            row = conn.execute(
                "SELECT c.* FROM wrytely_agent.source_connections c JOIN wrytely_agent.agents a "
                "ON a.id=c.agent_id WHERE a.user_id=%s AND c.id=%s",
                (verified_user, connection_id),
            ).fetchone()
        return _safe(row) if row else None

    def list_source_connections(self, verified_user, *, limit=20, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid connection list limit")
        with self.connection() as conn:
            anchor = None
            if cursor is not None:
                try:
                    cursor = UUID(str(cursor))
                except (ValueError, TypeError, AttributeError):
                    raise LookupError("Not found") from None
                anchor = conn.execute(
                    "SELECT c.created_at,c.id FROM wrytely_agent.source_connections c "
                    "JOIN wrytely_agent.agents a ON a.id=c.agent_id "
                    "WHERE a.user_id=%s AND c.id=%s",
                    (verified_user, cursor),
                ).fetchone()
                if anchor is None:
                    raise LookupError("Not found")
            rows = conn.execute(
                "SELECT c.* FROM wrytely_agent.source_connections c JOIN wrytely_agent.agents a "
                "ON a.id=c.agent_id WHERE a.user_id=%s "
                "AND (%s::timestamptz IS NULL OR (c.created_at,c.id)<(%s,%s::uuid)) "
                "ORDER BY c.created_at DESC,c.id DESC LIMIT %s",
                (
                    verified_user,
                    anchor["created_at"] if anchor else None,
                    anchor["created_at"] if anchor else None,
                    anchor["id"] if anchor else None,
                    limit + 1,
                ),
            ).fetchall()
        return {
            "connections": [_safe(row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }

    def rotate_or_revoke(self, verified_user, connection_id):
        """Revoke only. Credential replacement requires fresh authenticated pairing."""
        try:
            connection_id = UUID(str(connection_id))
        except (ValueError, TypeError, AttributeError):
            raise LookupError("Not found") from None
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE",
                (verified_user,),
            ).fetchone()
            row = conn.execute(
                "UPDATE wrytely_agent.source_connections SET generation=generation+1, "
                "state='disconnected',credential_hash=NULL,updated_at=clock_timestamp() "
                "WHERE id=%s AND agent_id=%s RETURNING *",
                (connection_id, agent["id"] if agent else None),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            self._reset_canvas_context(conn, row["id"])
            conn.execute(
                "UPDATE wrytely_agent.source_pairings SET consumed_at=clock_timestamp() "
                "WHERE agent_id=%s",
                (agent["id"],),
            )
        return _safe(row)
