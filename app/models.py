import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.workflow import Status

# Required text: surrounding spaces are removed, then it must not be empty.
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

# Deliberately loose: something@something.something. Full validation would need the email-validator package.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Input for POST /requests. due_date and status are never accepted from the client.
class RequestCreate(BaseModel):
    requester_name: ShortText
    requester_email: ShortText
    subject: LongText
    received_date: date

    @field_validator("requester_email")
    @classmethod
    def looks_like_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("requester_email must be an email address")
        return value

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
    working_days_left: int | None  # negative when overdue; None once the request is no longer open


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
