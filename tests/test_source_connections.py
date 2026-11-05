from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from shared.db import Store
from shared.source_connections import PairingLimited, PairingRejected, SourceCredentialRejected

ORIGIN = "https://canvas.example.edu"
OTHER_ORIGIN = "https://other.example.edu"


@pytest.fixture
def sources(store, alice):
    with store.connection() as conn:
        conn.execute("TRUNCATE wrytely_agent.source_pairing_rates")
    return Store(store._url, canvas_origins=(ORIGIN, OTHER_ORIGIN))


def pair(sources, user="user_alice", device="device-1"):
    challenge = sources.create_pairing(user, ORIGIN)
    return sources.redeem_pairing(challenge["code"], device)


def bind(sources, linked):
    return sources.bind_canvas_identity(linked["ingestion_bearer"], ORIGIN, "canvas-subject")


def test_pairing_binds_identity_and_exposes_only_safe_status(sources):
    linked = pair(sources)
    assert linked["state"] == "pending_identity"
    assert len(linked["ingestion_bearer"]) == 43
    bound = bind(sources, linked)
    assert bound["state"] == "connected"
    assert bound["generation"] == 1
    assert sources.source_connection("user_alice", bound["connection_id"]) == bound
    assert set(bound) == {
        "connection_id",
        "provider",
        "origin",
        "state",
        "generation",
        "credential_expires_at",
    }
    assert "canvas-subject" not in str(bound)
    assert "device-1" not in str(bound)


def test_database_retains_only_hashes_not_pairing_or_ingestion_secrets(sources):
    challenge = sources.create_pairing("user_alice", ORIGIN)
    linked = sources.redeem_pairing(challenge["code"], "device-1")
    with sources.connection() as conn:
        raw = str(conn.execute("SELECT * FROM wrytely_agent.source_pairings").fetchall())
        raw += str(conn.execute("SELECT * FROM wrytely_agent.source_connections").fetchall())
    assert challenge["code"] not in raw
    assert linked["ingestion_bearer"] not in raw


@pytest.mark.parametrize(
    "origin",
    [
        "http://canvas.example.edu",
        ORIGIN + "/",
        ORIGIN + "/courses",
        ORIGIN + "?x=1",
        "https://CANVAS.example.edu",
        "https://user:pass@canvas.example.edu",
        "https://canvas.example.edu:443",
        "https://canvas.example.edu#x",
        "not-a-url",
    ],
)
def test_origin_must_be_exact_configured_https_origin(sources, origin):
    with pytest.raises(ValueError):
        sources.create_pairing("user_alice", origin)
    with sources.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_pairings").fetchone()["n"]
            == 0
        )


def test_valid_but_unconfigured_origin_and_default_store_cannot_pair(sources, store):
    with pytest.raises(ValueError, match="not configured"):
        sources.create_pairing("user_alice", "https://unconfigured.example.edu")
    with pytest.raises(ValueError, match="not configured"):
        store.create_pairing("user_alice", ORIGIN)


def test_unprovisioned_user_cannot_pair(sources):
    with pytest.raises(LookupError, match="Complete setup"):
        sources.create_pairing("unknown-user", ORIGIN)


def test_new_code_invalidates_old_code_and_redemption_is_one_use(sources):
    first = sources.create_pairing("user_alice", ORIGIN)
    second = sources.create_pairing("user_alice", ORIGIN)
    for code in [first["code"], "x" * 32]:
        with pytest.raises(PairingRejected, match="^Invalid pairing$"):
            sources.redeem_pairing(code, "device-1")
    sources.redeem_pairing(second["code"], "device-1")
    with pytest.raises(PairingRejected, match="^Invalid pairing$"):
        sources.redeem_pairing(second["code"], "device-2")


def test_expired_code_cannot_create_connection(sources):
    code = sources.create_pairing("user_alice", ORIGIN)["code"]
    with sources.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_pairings SET expires_at=now()-interval '1 second'"
        )
    with pytest.raises(PairingRejected):
        sources.redeem_pairing(code, "device-1")
    with sources.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_connections").fetchone()[
                "n"
            ]
            == 0
        )


def test_pairing_issuance_has_persistent_window_even_after_redemption(sources):
    for _ in range(5):
        pair(sources)
    with pytest.raises(PairingLimited):
        sources.create_pairing("user_alice", ORIGIN)
    with sources.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_pairings SET window_started_at=now()-interval '11 minutes'"
        )
    assert pair(sources)["generation"] == 6


def test_failed_redemptions_commit_device_budget(sources):
    for _ in range(10):
        with pytest.raises(PairingRejected):
            sources.redeem_pairing("x" * 32, "device-1")
    code = sources.create_pairing("user_alice", ORIGIN)["code"]
    with pytest.raises(PairingLimited):
        sources.redeem_pairing(code, "device-1")
    # Throttling must not consume a valid challenge.
    assert sources.redeem_pairing(code, "device-2")["generation"] == 1


def test_random_device_ids_cannot_bypass_global_redemption_budget(sources):
    with sources.connection() as conn:
        conn.execute("INSERT INTO wrytely_agent.source_pairing_rates VALUES ('global',now(),120)")
    with pytest.raises(PairingLimited):
        sources.redeem_pairing("x" * 32, "fresh-device")
    with sources.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_pairing_rates").fetchone()[
                "n"
            ]
            == 1
        )


def test_redemption_rate_window_recovers(sources):
    with sources.connection() as conn:
        conn.execute(
            "INSERT INTO wrytely_agent.source_pairing_rates "
            "VALUES ('global',now()-interval '2 minutes',121)"
        )
    assert pair(sources)["state"] == "pending_identity"


def test_wrong_origin_cannot_bind_or_invalidate_connection(sources):
    linked = pair(sources)
    for origin in [OTHER_ORIGIN, "https://unconfigured.example.edu"]:
        with pytest.raises(SourceCredentialRejected):
            sources.bind_canvas_identity(linked["ingestion_bearer"], origin, "canvas-subject")
    assert bind(sources, linked)["state"] == "connected"


def test_same_subject_rebinding_is_idempotent_but_account_switch_revokes(sources):
    linked = pair(sources)
    assert bind(sources, linked) == bind(sources, linked)
    with pytest.raises(SourceCredentialRejected):
        sources.bind_canvas_identity(linked["ingestion_bearer"], ORIGIN, "other-subject")
    status = sources.source_connection("user_alice", linked["connection_id"])
    assert status["state"] == "reconnect_required"
    assert status["generation"] == 2
    with pytest.raises(SourceCredentialRejected):
        bind(sources, linked)


def test_expired_credential_requires_reconnect_and_cannot_bind(sources):
    linked = pair(sources)
    with sources.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_connections "
            "SET credential_expires_at=now()-interval '1 second'"
        )
    assert (
        sources.source_connection("user_alice", linked["connection_id"])["state"]
        == "reconnect_required"
    )
    with pytest.raises(SourceCredentialRejected):
        bind(sources, linked)


def test_repair_same_device_retains_connection_id_and_fences_old_credential(sources):
    first = pair(sources)
    bind(sources, first)
    second = pair(sources)
    assert second["connection_id"] == first["connection_id"]
    assert second["generation"] == 2
    assert second["state"] == "pending_identity"
    with pytest.raises(SourceCredentialRejected):
        bind(sources, first)
    assert bind(sources, second)["state"] == "connected"


def test_two_users_and_two_devices_are_independently_owned(sources):
    sources.provision("user_bob")
    alice = pair(sources)
    bob = pair(sources, "user_bob")
    assert alice["connection_id"] != bob["connection_id"]
    assert sources.source_connection("user_bob", alice["connection_id"]) is None
    assert sources.source_connection("user_alice", bob["connection_id"]) is None
    assert sources.source_connection("unprovisioned", alice["connection_id"]) is None
    with pytest.raises(LookupError, match="^Not found$"):
        sources.rotate_or_revoke("user_bob", alice["connection_id"])
    assert bind(sources, alice)["state"] == "connected"
    assert bind(sources, bob)["state"] == "connected"
    other_device = pair(sources, device="device-2")
    assert other_device["connection_id"] != alice["connection_id"]


def test_revoke_fences_credential_and_outstanding_pairing(sources):
    linked = pair(sources)
    bind(sources, linked)
    pending = sources.create_pairing("user_alice", ORIGIN)
    status = sources.rotate_or_revoke("user_alice", linked["connection_id"])
    assert status["state"] == "disconnected"
    assert status["generation"] == 2
    with pytest.raises(SourceCredentialRejected):
        bind(sources, linked)
    with pytest.raises(PairingRejected):
        sources.redeem_pairing(pending["code"], "device-2")
    assert pair(sources)["generation"] == 3


def test_concurrent_redemption_has_exactly_one_winner(sources):
    code = sources.create_pairing("user_alice", ORIGIN)["code"]
    barrier = Barrier(2)

    def redeem(device):
        barrier.wait(timeout=5)
        try:
            return sources.redeem_pairing(code, device)
        except PairingRejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, ["device-1", "device-2"]))
    assert sum(result is not None for result in results) == 1
    with sources.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_connections").fetchone()[
                "n"
            ]
            == 1
        )


def test_concurrent_bind_and_revoke_cannot_resurrect_revoked_credential(sources):
    linked = pair(sources)
    barrier = Barrier(2)

    def operation(which):
        barrier.wait(timeout=5)
        if which == "revoke":
            return sources.rotate_or_revoke("user_alice", linked["connection_id"])
        try:
            return bind(sources, linked)
        except SourceCredentialRejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(operation, ["bind", "revoke"]))
    assert (
        sources.source_connection("user_alice", linked["connection_id"])["state"] == "disconnected"
    )
    with pytest.raises(SourceCredentialRejected):
        bind(sources, linked)


def test_missing_and_nonowned_connections_have_same_private_read(sources):
    assert sources.source_connection("user_alice", str(uuid4())) is None
    assert sources.source_connection("user_alice", "not-a-uuid") is None


def test_migration_is_additive_and_replayable(sources):
    linked = pair(sources)
    sources.migrate()
    assert sources.source_connection("user_alice", linked["connection_id"])["generation"] == 1
    with sources.connection() as conn:
        versions = [
            r["version"]
            for r in conn.execute("SELECT version FROM wrytely_agent.migrations").fetchall()
        ]
    assert "010" in versions and "009" in versions
    assert "008" not in versions


@pytest.mark.parametrize("subject", [None, "", " padded", "x" * 1025, "a\x00b", "a\nb"])
def test_invalid_subject_does_not_consume_credential(sources, subject):
    linked = pair(sources)
    with pytest.raises(ValueError, match="provider subject"):
        sources.bind_canvas_identity(linked["ingestion_bearer"], ORIGIN, subject)
    assert bind(sources, linked)["state"] == "connected"


def test_insert_failure_rolls_back_challenge_consumption(sources, monkeypatch):
    first = pair(sources)
    code = sources.create_pairing("user_alice", ORIGIN)["code"]
    # Force a credential uniqueness collision after consuming the challenge.
    with monkeypatch.context() as patch:
        patch.setattr(
            "shared.source_connections.secrets.token_urlsafe", lambda _: first["ingestion_bearer"]
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            sources.redeem_pairing(code, "device-2")
    # The transaction, including challenge consumption, must have rolled back.
    linked = sources.redeem_pairing(code, "device-2")
    assert linked["connection_id"] != first["connection_id"]
    assert bind(sources, first)["state"] == "connected"


def test_removed_allowlist_blocks_previously_issued_codes_and_credentials(sources):
    linked = pair(sources)
    code = sources.create_pairing("user_alice", ORIGIN)["code"]
    without_origin = Store(sources._url)
    with pytest.raises(PairingRejected):
        without_origin.redeem_pairing(code, "device-2")
    with pytest.raises(SourceCredentialRejected):
        without_origin.bind_canvas_identity(linked["ingestion_bearer"], ORIGIN, "canvas-subject")


def test_invalid_revoke_ids_do_not_expose_database_errors(sources):
    with pytest.raises(LookupError, match="^Not found$"):
        sources.rotate_or_revoke("user_alice", "not-a-uuid")
