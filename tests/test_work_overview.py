from test_api import auth, make_client


def test_task_overview_is_private_and_survives_reconnect(store):
    client = make_client(store)
    assert client.get("/v1/tasks").status_code == 401
    store.provision("user_alice")
    store.provision("user_bob")
    store.enqueue("user_alice", "Private assignment " + "a" * 200, "one")
    lease = store.claim()
    store.complete(lease, "A saved result")
    store.enqueue("user_alice", "Next task", "two")
    tasks = client.get("/v1/tasks", headers=auth()).json()["tasks"]
    assert [task["status"] for task in tasks] == ["ready", "done"]
    assert tasks[0]["title"] == "Next task"
    assert len(tasks[1]["title"]) == 180
    assert "lease_token" not in tasks[0]
    assert client.get("/v1/tasks", headers=auth("bob")).json() == {"tasks": []}
    assert make_client(store).get("/v1/tasks", headers=auth()).json()["tasks"] == tasks


def test_task_overview_is_bounded(store):
    store.provision("user_alice")
    for number in range(53):
        store.enqueue("user_alice", f"Task {number}", str(number), limit=100)
    tasks = store.tasks("user_alice")
    assert len(tasks) == 50
    assert tasks[0]["title"] == "Task 52"
    assert tasks[-1]["title"] == "Task 3"
