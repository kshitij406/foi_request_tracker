# FOI Request Tracker

A small web app for logging Freedom of Information (FOI) requests, tracking their status, and flagging any that miss the statutory deadline.

Built with **FastAPI** and **SQLite**, plus a single-page HTML frontend that needs no build step.

## Features

- Log a request. The due date is set automatically to **20 working days** after receipt, skipping weekends and England & Wales bank holidays.
- Move requests through a fixed lifecycle. Invalid moves are rejected with `409` and a list of the moves that are allowed.
- Full history of every status change, with optional notes.
- Overdue flag for open requests that are past their due date.
- Summary counts by status.

## Status lifecycle

```
RECEIVED ──► IN_PROGRESS ──► RESPONDED ──► CLOSED
    │              │
    └──────────────┴──► WITHDRAWN
```

`CLOSED` and `WITHDRAWN` are final. Only `RECEIVED` and `IN_PROGRESS` requests can be overdue.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

- Web app: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs

The database (`foi.db`) is created on first run. Set `FOI_DB_PATH` to use a different file.

### Demo data

The repo ships with `foi.db` already seeded. To regenerate it (dates are relative to today, so overdue and due-soon requests stay realistic):

```bash
python -m app.seed --reset
```

This creates 12 requests covering every status, including a few overdue ones.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/requests` | Create a request (`requester_name`, `requester_email`, `subject`, `received_date`) |
| `GET`  | `/requests` | List requests, ordered by due date. Filters: `?status=IN_PROGRESS`, `?overdue=true` |
| `GET`  | `/requests/{id}` | One request with its event history |
| `POST` | `/requests/{id}/transitions` | Change status (`to_status`, optional `note`) |
| `GET`  | `/stats` | Count per status, plus `overdue` |

Example:

```bash
curl -X POST localhost:8000/requests \
  -H 'Content-Type: application/json' \
  -d '{"requester_name":"Jane Smith","requester_email":"jane@example.com","subject":"Parking revenue 2025","received_date":"2026-11-02"}'
```

## Project structure

```
app/
  main.py        FastAPI app: routes, error handlers, serves the frontend
  models.py      Pydantic request/response models
  repository.py  All SQL queries
  workflow.py    Status enum and allowed transitions
  deadlines.py   Working-day and due-date calculation
  db.py          SQLite connection helpers
  seed.py        Demo data loader
static/
  index.html     Frontend (HTML/CSS/vanilla JS, calls the API)
data/
  bank-holidays.json   gov.uk bank holiday data
schema.sql       Database tables and indexes
tests/           Unit and API tests (conftest.py sets up a temp DB per test)
```

## Tests

```bash
pytest -v
```

- `test_deadlines.py`: due-date rules (weekends, bank holidays, Christmas, Easter, received on a weekend)
- `test_workflow.py`: allowed and forbidden status moves
- `test_api.py`: endpoints end to end. Each test gets its own temporary database (see `tests/conftest.py`), so `foi.db` is never touched.
