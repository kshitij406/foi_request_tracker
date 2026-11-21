import os
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db, repository
from app.deadlines import foi_due_date, load_bank_holidays
from app.models import RequestCreate, RequestDetail, RequestOut, TransitionIn
from app.workflow import ALLOWED_TRANSITIONS, InvalidTransition, RequestNotFound, Status
from pydantic import ValidationError

ROOT = Path(__file__).parent.parent
HOLIDAYS_PATH = ROOT / "data" / "bank-holidays.json"
SCHEMA_PATH = ROOT / "schema.sql"
TEMPLATES_PATH = Path(__file__).parent / "templates"

# Only open requests can be overdue.
OPEN_STATUSES = {Status.RECEIVED.value, Status.IN_PROGRESS.value}

app = FastAPI(title="FOI Request Tracker")
templates = Jinja2Templates(directory=TEMPLATES_PATH)

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


# HTML pages for non-developers. Same repository calls as the API, rendered server-side.
# Forms post back and redirect (303) on success, so refreshing never resubmits.

def render_list(request, conn, status=None, overdue=False, form=None, error=None, code=200):
    today = date.today()
    rows = repository.list_requests(conn, status=status, overdue=overdue, today=today)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "requests": [to_request_out(row, today) for row in rows],
            "stats": repository.count_by_status(conn, today),
            "statuses": list(Status),
            "selected": status,
            "overdue": overdue,
            "today": today,
            "form": form or {},
            "error": error,
        },
        status_code=code,
    )


def render_detail(request, conn, request_id, error=None, code=200):
    row = repository.get_request(conn, request_id)
    if row is None:
        raise RequestNotFound(request_id)
    today = date.today()
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "r": to_request_out(row, today),
            "events": repository.get_events(conn, request_id),
            "next_moves": [s for s in Status if s in ALLOWED_TRANSITIONS[Status(row["status"])]],
            "today": today,
            "error": error,
        },
        status_code=code,
    )


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    status: Status | None = None,
    overdue: bool = False,
    conn=Depends(db.get_db),
):
    return render_list(request, conn, status=status, overdue=overdue)


@app.post("/new", response_class=HTMLResponse)
def create_from_form(
    request: Request,
    requester_name: str = Form(),
    requester_email: str = Form(),
    subject: str = Form(),
    received_date: str = Form(),
    conn=Depends(db.get_db),
):
    form = {
        "requester_name": requester_name,
        "requester_email": requester_email,
        "subject": subject,
        "received_date": received_date,
    }
    try:
        data = RequestCreate(**form)
    except ValidationError as exc:
        # Re-show the form with what was typed and the first validation message.
        message = exc.errors()[0]["msg"].removeprefix("Value error, ")
        return render_list(request, conn, form=form, error=message, code=422)

    new_id = repository.create_request(conn, data, foi_due_date(data.received_date, HOLIDAYS))
    return RedirectResponse(f"/requests/{new_id}/view", status_code=303)


@app.get("/requests/{request_id}/view", response_class=HTMLResponse)
def detail_page(request: Request, request_id: int, conn=Depends(db.get_db)):
    return render_detail(request, conn, request_id)


@app.post("/requests/{request_id}/move", response_class=HTMLResponse)
def move_from_form(
    request: Request,
    request_id: int,
    to_status: Status = Form(),
    note: str = Form(""),
    conn=Depends(db.get_db),
):
    try:
        repository.apply_transition(conn, request_id, to_status, note.strip() or None)
    except InvalidTransition as exc:
        # Only reachable from a stale page; the buttons only offer allowed moves.
        return render_detail(request, conn, request_id, error=str(exc), code=409)
    return RedirectResponse(f"/requests/{request_id}/view", status_code=303)
