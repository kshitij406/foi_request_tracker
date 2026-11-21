"""Fill the database with demo requests.

    python -m app.seed            # only if the database is empty
    python -m app.seed --reset    # wipe existing requests first

Dates are relative to today, so the overdue / due-soon mix stays realistic whenever it's run.
"""
import os
import sys
from datetime import date, timedelta

from app import db, repository
from app.deadlines import foi_due_date, load_bank_holidays
from app.main import HOLIDAYS_PATH, SCHEMA_PATH
from app.models import RequestCreate
from app.workflow import Status

# (name, email, subject, days ago received, [(status, note), ...] applied in order)
SEED = [
    ("Jane Smith", "jane.smith@example.com", "Council parking revenue 2025", 50,
     [(Status.IN_PROGRESS, "Passed to finance team")]),
    ("Omar Haddad", "o.haddad@example.com", "Number of potholes reported on A-roads", 45, []),
    ("Priya Patel", "priya.p@example.com", "Spending on agency staff in social care", 40,
     [(Status.IN_PROGRESS, None)]),
    ("Tom Walker", "tom.walker@example.com", "School meal supplier contracts", 30,
     [(Status.IN_PROGRESS, "Awaiting contracts from procurement")]),
    ("Grace Okafor", "grace.okafor@example.com", "Air quality monitoring data 2024-2026", 21, []),
    ("Liam Murphy", "liam.m@example.com", "Library closure consultation responses", 14,
     [(Status.IN_PROGRESS, None)]),
    ("Sophie Chen", "sophie.chen@example.com", "Councillor expense claims Q2 2026", 7, []),
    ("Daniel Evans", "d.evans@example.com", "Housing waiting list numbers by ward", 2, []),
    ("Aisha Rahman", "aisha.r@example.com", "Fly-tipping fines issued in 2025", 60,
     [(Status.IN_PROGRESS, None), (Status.RESPONDED, "Figures sent by email")]),
    ("Mark Davies", "mark.davies@example.com", "IT outsourcing contract value", 75,
     [(Status.IN_PROGRESS, None), (Status.RESPONDED, "Partial disclosure, s.43 commercial interests"),
      (Status.CLOSED, "No appeal received")]),
    ("Emily Brown", "emily.b@example.com", "Street lighting energy costs", 90,
     [(Status.IN_PROGRESS, None), (Status.RESPONDED, None), (Status.CLOSED, None)]),
    ("Ravi Kumar", "ravi.kumar@example.com", "Planning enforcement complaints 2025", 35,
     [(Status.WITHDRAWN, "Requester found the data published online")]),
]


def main() -> None:
    conn = db.get_connection(os.environ.get("FOI_DB_PATH", "foi.db"))
    db.init_db(conn, SCHEMA_PATH)

    existing = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    if existing:
        if "--reset" not in sys.argv:
            sys.exit(f"Database already has {existing} requests. Use --reset to wipe and reseed.")
        with conn:
            conn.execute("DELETE FROM events")  # events first: they reference requests
            conn.execute("DELETE FROM requests")
            conn.execute("DELETE FROM sqlite_sequence")  # restart ids at 1

    holidays = load_bank_holidays(HOLIDAYS_PATH)
    today = date.today()

    for name, email, subject, days_ago, steps in SEED:
        data = RequestCreate(
            requester_name=name,
            requester_email=email,
            subject=subject,
            received_date=today - timedelta(days=days_ago),
        )
        # Go through the repository so due dates and history events match real usage.
        request_id = repository.create_request(conn, data, foi_due_date(data.received_date, holidays))
        for status, note in steps:
            repository.apply_transition(conn, request_id, status, note)

    print(f"Seeded {len(SEED)} requests.")
    conn.close()


if __name__ == "__main__":
    main()
