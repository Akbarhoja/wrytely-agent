from runtime.preflight import database_check


def test_actual_migration_ledger_matches_without_changing_student_data(store, alice):
    before = store.agent(alice["user_id"])
    assert database_check(store._url) == {
        "state": "verified",
        "reason": "migration_ledger_matches",
    }
    assert store.agent(alice["user_id"]) == before
