from datetime import date

from app.workflow import InvalidTransition, RequestNotFound, Status, check_transition


# Request row and its first history event are written in one transaction (`with conn`).
def create_request(conn, data, due_date) -> int:
    with conn:
        cur = conn.execute(
            """
            INSERT INTO requests (requester_name, requester_email, subject, received_date, due_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data.requester_name,
                data.requester_email,
                data.subject,
                data.received_date.isoformat(),
                due_date.isoformat(),
            ),
        )
        new_id = cur.lastrowid

        conn.execute(
            "INSERT INTO events (request_id, from_status, to_status) VALUES (?, ?, ?)",
            (new_id, None, Status.RECEIVED.value),
        )

    return new_id


def get_request(conn, request_id) -> dict | None:
    cur = conn.execute(
        """
        SELECT id, requester_name, requester_email, subject, received_date,
               due_date, status, assigned_to, created_at
        FROM requests
        WHERE id = ?
        """,
        (request_id,),
    )
    row = cur.fetchone()

    if row is None:
        return None
    return dict(row)


def get_events(conn, request_id) -> list[dict]:
    cur = conn.execute(
        """
        SELECT id, request_id, from_status, to_status, note, created_at
        FROM events
        WHERE request_id = ?
        ORDER BY id DESC  -- newest first
        """,
        (request_id,),
    )
    rows = cur.fetchall()

    return [dict(r) for r in rows]


def list_requests(conn, status=None, overdue=False, today=None) -> list[dict]:
    query = "SELECT * FROM requests"
    conditions = []
    params = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)

    if overdue:
        if today is None:
            raise ValueError("today is required when overdue=True")
        # Overdue = past due and still open. Responded/closed/withdrawn requests are never overdue.
        conditions.append("due_date < ?")
        params.append(today.isoformat())
        conditions.append("status IN (?, ?)")
        params.append(Status.RECEIVED.value)
        params.append(Status.IN_PROGRESS.value)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY due_date"  # most urgent first

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def apply_transition(conn, request_id, target, note=None) -> dict:
    with conn:
        row = conn.execute(
            "SELECT status FROM requests WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise RequestNotFound(request_id)

        current = Status(row["status"])
        check_transition(current, target)

        # "AND status = ?" guards against a concurrent update between the SELECT and this UPDATE.
        cur = conn.execute(
            "UPDATE requests SET status = ? WHERE id = ? AND status = ?",
            (target.value, request_id, current.value),
        )
        if cur.rowcount != 1:
            raise InvalidTransition(current, target)

        conn.execute(
            "INSERT INTO events (request_id, from_status, to_status, note) VALUES (?, ?, ?, ?)",
            (request_id, current.value, target.value, note),
        )

    return get_request(conn, request_id)


def count_by_status(conn, today: date) -> dict:
    counts = {s.value: 0 for s in Status}

    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM requests GROUP BY status"
    ).fetchall()
    for row in rows:
        counts[row["status"]] = row["n"]

    counts["overdue"] = len(list_requests(conn, overdue=True, today=today))
    return counts