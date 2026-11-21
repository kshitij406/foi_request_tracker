from datetime import date

from pydantic import BaseModel, field_validator

from app.workflow import Status


# Input for POST /requests. due_date and status are never accepted from the client.
class RequestCreate(BaseModel):
    requester_name: str
    requester_email: str
    subject: str
    received_date: date

    @field_validator("received_date")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("received_date cannot be in the future")
        return value


class RequestOut(BaseModel):
    id: int
    requester_name: str
    requester_email: str
    subject: str
    received_date: date
    due_date: date
    status: Status
    assigned_to: str | None
    created_at: str
    is_overdue: bool  # computed per request, not stored, so it never goes stale


class EventOut(BaseModel):
    id: int
    request_id: int
    from_status: Status | None
    to_status: Status
    note: str | None
    created_at: str


class RequestDetail(RequestOut):
    events: list[EventOut]


class TransitionIn(BaseModel):
    to_status: Status
    note: str | None = None