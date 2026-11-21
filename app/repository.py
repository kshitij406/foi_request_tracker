from app.workflow import Status

def create_request(conn, data, due_date) -> int:
    with conn:
        cur = conn.execute("""
                 INSERT INTO requests (requester_name, requester_email, subject, received_date, due_date) VALUES(?, ?, ?, ?, ?)""",
                 (
                    data.requester_name,
                    data.requester_email,
                    data.subject,
                    data.received_date.isoformat(),
                    due_date.isoformat(),
                ))
        
        new_id = cur.lastrowid
        
        conn.execute(
            "INSERT INTO events (request_id, from_status, to_status) VALUES (?, ?, ?)",
            (new_id, None, Status.RECEIVED.value),
        )
        
    return new_id

def get_request(conn, request_id) -> dict | None:
    
    cur = conn.execute("""
                        SELECT id, requester_name, requester_email, subject, received_date, due_date, status, assigned_to, created_at FROM requests WHERE id = ?
                        """, (request_id,))
    
    row = cur.fetchone()
    
    if row is None:
        return None
    else:
        return dict(row)
    
    
def get_events(conn, request_id) -> list[dict]:

    cur = conn.execute("""
                        SELECT id, request_id, from_status, to_status, note, created_at FROM events WHERE request_id = ? ORDER BY id DESC
                        """, (request_id,))
    row = cur.fetchall()
    
    return [dict(r) for r in row]
        
        