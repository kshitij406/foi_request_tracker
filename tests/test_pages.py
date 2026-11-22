from datetime import date, timedelta

FORM = {
    "requester_name": "Jane Smith",
    "requester_email": "jane@example.com",
    "subject": "Parking revenue",
    "received_date": "2026-11-02",
}


def test_list_page_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "<table>" in res.text


def test_create_form_redirects_to_detail_page(client):
    res = client.post("/new", data=FORM, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/requests/1/view"

    page = client.get("/requests/1/view")
    assert "Parking revenue" in page.text
    assert "01 Dec 2026" in page.text  # due date shown


def test_create_form_rejects_future_date_and_keeps_input(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = client.post("/new", data={**FORM, "received_date": tomorrow})
    assert res.status_code == 422
    assert "cannot be in the future" in res.text
    assert 'value="Parking revenue"' in res.text
    assert client.get("/requests").json() == []


def test_detail_page_offers_only_allowed_moves(client):
    client.post("/new", data=FORM)
    page = client.get("/requests/1/view").text
    assert 'value="IN_PROGRESS"' in page
    assert 'value="WITHDRAWN"' in page
    assert 'value="CLOSED"' not in page


def test_move_form_changes_status_and_records_note(client):
    client.post("/new", data=FORM)
    res = client.post("/requests/1/move", data={"to_status": "IN_PROGRESS", "note": "With records team"}, follow_redirects=False)
    assert res.status_code == 303

    detail = client.get("/requests/1").json()
    assert detail["status"] == "IN_PROGRESS"
    assert detail["events"][0]["note"] == "With records team"


def test_invalid_move_form_shows_error_and_changes_nothing(client, conn):
    client.post("/new", data=FORM)
    res = client.post("/requests/1/move", data={"to_status": "CLOSED"})
    assert res.status_code == 409
    assert "Cannot transition from RECEIVED to CLOSED" in res.text
    assert client.get("/requests/1").json()["status"] == "RECEIVED"
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_unknown_request_page_is_an_html_404(client):
    res = client.get("/requests/999/view")
    assert res.status_code == 404
    assert "Request not found" in res.text


def test_tampered_status_in_form_shows_error_page(client):
    client.post("/new", data=FORM)
    res = client.post("/requests/1/move", data={"to_status": "BOGUS"})
    assert res.status_code == 422
    assert "Unknown status: BOGUS" in res.text
