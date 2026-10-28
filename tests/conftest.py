import os

import pytest

from shared.db import Store


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    url = os.environ.get("AGENT_TEST_DATABASE_URL")
    if url:
        if os.environ.get("AGENT_TEST_ALLOW_RESET") != "yes":
            pytest.fail("External test database requires AGENT_TEST_ALLOW_RESET=yes")
        yield url
        return
    try:
        import pgserver
    except ImportError:
        pytest.fail("Provide isolated AGENT_TEST_DATABASE_URL or install pgserver on macOS")
    server = pgserver.get_server(tmp_path_factory.mktemp("agent-pg"), cleanup_mode="delete")
    yield server.get_uri()
    server.cleanup()


@pytest.fixture
def store(database_url):
    store = Store(database_url)
    store.migrate()
    with store.connection() as conn:
        conn.execute("TRUNCATE wrytely_agent.students CASCADE")
    yield store


@pytest.fixture
def alice(store):
    return store.provision("user_alice")
