import os
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db, repository
from app.deadlines import foi_due_date, load_bank_holidays
from app.models import RequestCreate, RequestDetail, RequestOut, TransitionIn
from app.workflow import InvalidTransition, RequestNotFound, Status

ROOT = Path(__file__).parent.parent
HOLIDAYS_PATH = ROOT / "data" / "bank-holidays.json"
SCHEMA_PATH = ROOT / "schema.sql"
STATIC_PATH = ROOT / "static"

# Only open requests can be overdue.
OPEN_STATUSES = {Status.RECEIVED.value, Status.IN_PROGRESS.value}

app = FastAPI(title="FOI Request Tracker")

# Runs once when the server starts: load holidays and make sure the tables exist.
HOLIDAYS = load_bank_holidays(HOLIDAYS_PATH)

startup_conn = db.get_connection(os.environ.get("FOI_DB_PATH", "foi.db"))
db.init_db(startup_conn, SCHEMA_PATH)
startup_conn.close()


def is_overdue(row: dict, today: date) -> bool:
    return row["due_date"] < today.isoformat() and row["status"] in OPEN_STATUSES


def to_request_out(row: dict, today: date) -> RequestOut:
    return RequestOut(**row, is_overdue=is_overdue(row, today))


# Error handlers: turn domain exceptions into HTTP responses.

@app.exception_handler(RequestNotFound)
def handle_not_found(request: Request, exc: RequestNotFound):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "request_id": exc.request_id},
    )


@app.exception_handler(InvalidTransition)
def handle_invalid_transition(request: Request, exc: InvalidTransition):
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "current_status": exc.current.value,
            "requested_status": exc.target.value,
            "allowed": sorted(s.value for s in exc.allowed),
        },
    )


# API endpoints.

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/requests", status_code=201, response_model=RequestOut)
def create_request(data: RequestCreate, conn=Depends(db.get_db)):
    due = foi_due_date(data.received_date, HOLIDAYS)
    new_id = repository.create_request(conn, data, due)
    row = repository.get_request(conn, new_id)
    return to_request_out(row, date.today())


@app.get("/requests", response_model=list[RequestOut])
def list_requests(
    status: Status | None = None,
    overdue: bool = False,
    conn=Depends(db.get_db),
):
    today = date.today()
    rows = repository.list_requests(conn, status=status, overdue=overdue, today=today)
    return [to_request_out(row, today) for row in rows]


@app.get("/requests/{request_id}", response_model=RequestDetail)
def get_request(request_id: int, conn=Depends(db.get_db)):
    row = repository.get_request(conn, request_id)
    if row is None:
        raise RequestNotFound(request_id)
    events = repository.get_events(conn, request_id)
    return RequestDetail(**row, is_overdue=is_overdue(row, date.today()), events=events)


@app.post("/requests/{request_id}/transitions", response_model=RequestOut)
def transition_request(request_id: int, body: TransitionIn, conn=Depends(db.get_db)):
    row = repository.apply_transition(conn, request_id, body.to_status, body.note)
    return to_request_out(row, date.today())


@app.get("/stats")
def stats(conn=Depends(db.get_db)):
    return repository.count_by_status(conn, date.today())


# Frontend: serves static/index.html at "/". Mounted last so API routes take priority.

app.mount("/", StaticFiles(directory=STATIC_PATH, html=True), name="static")
