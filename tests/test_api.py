from datetime import date, timedelta


def make_request(client, received_date="2026-11-02", **overrides):
    body = {
        "requester_name": "Jane Smith",
        "requester_email": "jane@example.com",
        "subject": "Parking revenue",
        "received_date": received_date,
        **overrides,
    }
    return client.post("/requests", json=body)


def move(client, request_id, to_status, note=None):
    return client.post(f"/requests/{request_id}/transitions", json={"to_status": to_status, "note": note})


def event_count(conn, request_id):
    return conn.execute("SELECT COUNT(*) FROM events WHERE request_id = ?", (request_id,)).fetchone()[0]


def test_create_returns_201_and_due_date(client):
    res = make_request(client, received_date="2026-11-02")
    assert res.status_code == 201
    body = res.json()
    assert body["due_date"] == "2026-12-01"  # St Andrew's Day, 30 Nov, is skipped
    assert body["status"] == "RECEIVED"


def test_create_rejects_future_received_date(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = make_request(client, received_date=tomorrow)
    assert res.status_code == 422


def test_get_unknown_request_returns_404(client):
    res = client.get("/requests/999")
    assert res.status_code == 404


def test_creation_writes_one_event(client, conn):
    request_id = make_request(client).json()["id"]
    assert event_count(conn, request_id) == 1

    events = client.get(f"/requests/{request_id}").json()["events"]
    assert events[0]["from_status"] is None
    assert events[0]["to_status"] == "RECEIVED"


def test_valid_transition_updates_status_and_writes_event(client, conn):
    request_id = make_request(client).json()["id"]

    res = move(client, request_id, "IN_PROGRESS", note="Assigned to records team")
    assert res.status_code == 200
    assert res.json()["status"] == "IN_PROGRESS"

    assert event_count(conn, request_id) == 2
    latest = client.get(f"/requests/{request_id}").json()["events"][0]  # newest first
    assert latest["from_status"] == "RECEIVED"
    assert latest["to_status"] == "IN_PROGRESS"
    assert latest["note"] == "Assigned to records team"


def test_invalid_transition_returns_409_and_changes_nothing(client, conn):
    request_id = make_request(client).json()["id"]
    events_before = event_count(conn, request_id)

    res = move(client, request_id, "CLOSED")
    assert res.status_code == 409
    assert sorted(res.json()["allowed"]) == ["IN_PROGRESS", "WITHDRAWN"]

    assert client.get(f"/requests/{request_id}").json()["status"] == "RECEIVED"
    assert event_count(conn, request_id) == events_before


def test_overdue_filter_returns_only_open_late_requests(client):
    # Received long ago, so these are past due whatever today is.
    late_received = make_request(client, received_date="2025-01-06", subject="late received").json()["id"]
    late_in_progress = make_request(client, received_date="2025-01-06", subject="late in progress").json()["id"]
    move(client, late_in_progress, "IN_PROGRESS")
    late_withdrawn = make_request(client, received_date="2025-01-06", subject="late withdrawn").json()["id"]
    move(client, late_withdrawn, "WITHDRAWN")
    # Received today, so due 20 working days from now.
    make_request(client, received_date=date.today().isoformat(), subject="not due yet")

    res = client.get("/requests", params={"overdue": "true"})
    assert res.status_code == 200
    ids = {r["id"] for r in res.json()}
    assert ids == {late_received, late_in_progress}
    assert all(r["is_overdue"] for r in res.json())


def test_responded_request_is_never_overdue(client):
    request_id = make_request(client, received_date="2025-01-06").json()["id"]
    move(client, request_id, "IN_PROGRESS")
    res = move(client, request_id, "RESPONDED")

    assert res.json()["is_overdue"] is False
    assert client.get("/requests", params={"overdue": "true"}).json() == []
    assert client.get("/stats").json()["overdue"] == 0


def test_create_rejects_blank_name_and_bad_email(client):
    assert make_request(client, requester_name="   ").status_code == 422
    assert make_request(client, requester_email="not-an-email").status_code == 422


def test_create_rejects_date_outside_holiday_data(client):
    res = make_request(client, received_date="2018-01-02")
    assert res.status_code == 422
    assert "Bank holiday data covers" in res.json()["detail"]


def test_overdue_request_has_negative_working_days_left(client):
    body = make_request(client, received_date="2025-01-06").json()
    assert body["is_overdue"] is True
    assert body["working_days_left"] < 0


def test_blank_note_is_stored_as_null(client):
    request_id = make_request(client).json()["id"]
    move(client, request_id, "IN_PROGRESS", note="   ")
    assert client.get(f"/requests/{request_id}").json()["events"][0]["note"] is None
