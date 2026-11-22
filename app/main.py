import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app import db, repository
from app.deadlines import HolidayDataOutOfRange, foi_due_date, load_bank_holidays, working_days_left
from app.models import RequestCreate, RequestDetail, RequestOut, TransitionIn
from app.workflow import ALLOWED_TRANSITIONS, InvalidTransition, RequestNotFound, Status

ROOT = Path(__file__).parent.parent
HOLIDAYS_PATH = ROOT / "data" / "bank-holidays.json"
SCHEMA_PATH = ROOT / "schema.sql"
TEMPLATES_PATH = Path(__file__).parent / "templates"

# Only open requests can be overdue.
OPEN_STATUSES = {Status.RECEIVED.value, Status.IN_PROGRESS.value}

# Loaded once. Reading a file has no side effects, so this is safe at import time.
HOLIDAYS = load_bank_holidays(HOLIDAYS_PATH)


# Runs when the server starts, not when the module is imported, so importing app.main
# (in tests or seed.py) never touches a database.
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.get_connection(os.environ.get("FOI_DB_PATH", "foi.db"))
    db.init_db(conn, SCHEMA_PATH)
    conn.close()
    yield


app = FastAPI(title="FOI Request Tracker", lifespan=lifespan)
templates = Jinja2Templates(directory=TEMPLATES_PATH)


def is_overdue(row: dict, today: date) -> bool:
    return row["due_date"] < today.isoformat() and row["status"] in OPEN_STATUSES


def to_request_out(row: dict, today: date) -> RequestOut:
    left = None
    if row["status"] in OPEN_STATUSES:
        left = working_days_left(today, date.fromisoformat(row["due_date"]), HOLIDAYS)
    return RequestOut(**row, is_overdue=is_overdue(row, today), working_days_left=left)


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


@app.exception_handler(HolidayDataOutOfRange)
def handle_holiday_range(request: Request, exc: HolidayDataOutOfRange):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


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
    return RequestDetail(**to_request_out(row, date.today()).model_dump(), events=events)


@app.post("/requests/{request_id}/transitions", response_model=RequestOut)
def transition_request(request_id: int, body: TransitionIn, conn=Depends(db.get_db)):
    row = repository.apply_transition(conn, request_id, body.to_status, body.note)
    return to_request_out(row, date.today())


@app.get("/stats")
def stats(conn=Depends(db.get_db)):
    return repository.count_by_status(conn, date.today())


# HTML pages for non-developers. Same repository calls as the API, rendered server-side.
# Forms post back and redirect (303) on success, so refreshing never resubmits.
# Errors on these routes are shown as pages, never as raw JSON.

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
        return templates.TemplateResponse(request, "missing.html", {"request_id": request_id}, status_code=404)
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
        due = foi_due_date(data.received_date, HOLIDAYS)
    except ValidationError as exc:
        # Re-show the form with what was typed and the first validation message.
        message = exc.errors()[0]["msg"].removeprefix("Value error, ")
        return render_list(request, conn, form=form, error=message, code=422)
    except HolidayDataOutOfRange as exc:
        return render_list(request, conn, form=form, error=str(exc), code=422)

    new_id = repository.create_request(conn, data, due)
    return RedirectResponse(f"/requests/{new_id}/view", status_code=303)


@app.get("/requests/{request_id}/view", response_class=HTMLResponse)
def detail_page(request: Request, request_id: int, conn=Depends(db.get_db)):
    return render_detail(request, conn, request_id)


@app.post("/requests/{request_id}/move", response_class=HTMLResponse)
def move_from_form(
    request: Request,
    request_id: int,
    to_status: str = Form(),  # a plain string, so a tampered value gets a page, not FastAPI's JSON 422
    note: str = Form(""),
    conn=Depends(db.get_db),
):
    try:
        target = Status(to_status)
    except ValueError:
        return render_detail(request, conn, request_id, error=f"Unknown status: {to_status}", code=422)
    try:
        repository.apply_transition(conn, request_id, target, note)
    except InvalidTransition as exc:
        # Only reachable from a stale page; the buttons only offer allowed moves.
        return render_detail(request, conn, request_id, error=str(exc), code=409)
    except RequestNotFound:
        return render_detail(request, conn, request_id)  # shows the 404 page
    return RedirectResponse(f"/requests/{request_id}/view", status_code=303)
