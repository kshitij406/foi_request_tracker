# FOI Request Tracker

A small backend for logging Freedom of Information (FOI) requests. It calculates each request's 20-working-day legal deadline, enforces a status workflow, keeps an audit history of every change and flags overdue requests.

Built with **FastAPI**, **SQLite** (raw SQL through `sqlite3`, no ORM), **Pydantic** and server-rendered **Jinja2** pages. `python-multipart` is the one extra dependency, needed to read HTML form posts.

## How to run

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python seed.py              # reset foi.db with 12 demo requests
uvicorn app.main:app --reload
```

- Request list page: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs

The database path defaults to `foi.db`. Set `FOI_DB_PATH` to use another file. Tables are created automatically on startup.

## Status workflow

```
RECEIVED ──► IN_PROGRESS ──► RESPONDED ──► CLOSED
    │              │
    └──────────────┴──► WITHDRAWN
```

Any other move, including moving to the same status, returns `409` with the allowed moves. `CLOSED` and `WITHDRAWN` are final.

**Deadline:** due on the 20th working day after receipt. The day of receipt is not counted, and weekends and bank holidays are skipped. Under FOIA s.10(6) a bank holiday in any part of the UK counts, so the England & Wales, Scotland and Northern Ireland lists are all used (St Andrew's Day and St Patrick's Day included). If a request arrives on a weekend or bank holiday, the count starts from the next working day, following ICO guidance (tested in `test_received_on_weekend`).

**Overdue:** `due_date < today` and status is `RECEIVED` or `IN_PROGRESS`. Responded, closed and withdrawn requests are never overdue.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/requests` | Create a request (`requester_name`, `requester_email`, `subject`, `received_date`). Returns 201 with the calculated `due_date`. Future dates give 422. |
| `GET`  | `/requests` | List requests, soonest due first. Filters: `?status=IN_PROGRESS`, `?overdue=true` |
| `GET`  | `/requests/{id}` | One request with its event history (404 if unknown) |
| `POST` | `/requests/{id}/transitions` | Change status (`to_status`, optional `note`). 404 if unknown, 409 if the move is not allowed. |
| `GET`  | `/stats` | Count per status, plus `overdue` |

### HTML pages

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | List of requests: overdue rows in red, filter links, a "Log a new request" form |
| `POST` | `/new` | Form target for creating a request. Redirects to its detail page, or shows the error and keeps what was typed. |
| `GET`  | `/requests/{id}/view` | Detail page: request details, a button for each allowed move, history |
| `POST` | `/requests/{id}/move` | Form target for a status change, with an optional note |

The pages use plain HTML forms, no JavaScript. They call the same repository functions as the API, so the same rules apply.

## Design decisions

- **SQL only in `repository.py`, HTTP only in `main.py`.** The repository returns plain dicts and raises domain exceptions (`RequestNotFound`, `InvalidTransition`), and `main.py` maps those to 404 and 409. Each layer can be read and tested on its own, and swapping the database would only touch one file.
- **The due date is calculated once, at creation, and stored.** It is a legal deadline fixed when the request arrives, so later changes to the holiday file don't silently move existing deadlines. Storing it also makes the overdue filter a simple indexed `due_date < ?` query.
- **`ALLOWED_TRANSITIONS` is the single source of truth.** One dict in `workflow.py` defines the whole lifecycle. `check_transition` and the 409 error body both read from it.
- **Status change and audit event in one transaction.** `apply_transition` reads the status, checks the move, updates with `WHERE id = ? AND status = ?` (so a concurrent change can't be overwritten), checks `rowcount == 1` and inserts the event inside one `with conn:` block. On any error the whole thing rolls back, so a failed transition changes nothing.
- **`today` is passed in, not read inside the logic.** `list_requests` and `count_by_status` take `today` as an argument, so the overdue rules can be tested with any date.
- **Dates stored as ISO text (`YYYY-MM-DD`).** ISO dates sort and compare correctly as strings in SQLite.
- **`is_overdue` is computed per response, not stored.** A stored flag would go stale overnight.

## Known limitations

- **Dates mix two clocks.** `date.today()` uses the server's local date; `created_at` is UTC from SQLite.
- **No pagination or CSRF protection** yet.

- **No authentication or roles.** Anyone who can reach the API can change any request. This is the first thing to add.
- **Clarification rule not implemented.** Under the FOI Act the 20-day clock restarts when a requester replies to a clarification request. There is no `AWAITING_CLARIFICATION` status yet.
- **The holiday list is a static file.** `data/bank-holidays.json` covers 2019 to 2028 and has to be refreshed. Outside that range the app refuses to calculate a due date (422) rather than guess.
- **SQLite allows one writer at a time.** Fine for a demo; production would use Postgres.
- **`assigned_to` exists but there is no endpoint to set it.**
- **`foi.db` is committed** so the demo works straight from a clone. A real deployment would ignore `*.db`.

## Project structure

```
app/
  main.py            FastAPI app: routes, error handlers, HTML page
  models.py          Pydantic request/response models
  repository.py      All SQL queries
  workflow.py        Status enum, allowed transitions, exceptions
  deadlines.py       Working-day and due-date calculation
  db.py              SQLite connection, init_db, get_db dependency
  templates/
    base.html        Shared layout and styles
    index.html       List page with the new-request form
    detail.html      One request: details, allowed moves, history
data/
  bank-holidays.json gov.uk bank holiday data
tests/
  conftest.py        Temporary database and TestClient fixtures
  test_deadlines.py
  test_workflow.py
  test_api.py
  test_pages.py      HTML forms: create, move, error handling
schema.sql           Tables and indexes
seed.py              Demo data loader
```

## Tests

```bash
pytest -v
```

36 tests cover the deadline rules (including Christmas and Easter), the workflow rules, the API end to end and the HTML forms. Each API test runs against its own temporary database, so `foi.db` is never touched.
