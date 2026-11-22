import json
from datetime import date
from datetime import timedelta


class HolidayDataOutOfRange(ValueError):
    """The date falls outside the years the bank holiday file covers, so a due date would be a guess."""


# Loads bank holidays from the gov.uk JSON (data/bank-holidays.json).
# FOIA s.10(6): a working day excludes a bank holiday "in any part of the United Kingdom",
# so all three lists count: England and Wales, Scotland, and Northern Ireland.
def load_bank_holidays(path:str) -> set[date]:
    with open(path, mode="r", encoding="utf-8") as file:
        data = json.load(file)

    bank_holidays = set()

    for region in data.values():
        for event in region["events"]:
            bank_holidays.add(date.fromisoformat(event["date"]))

    return bank_holidays

# Checks if a given date is a working date or not
def is_working_day(d: date, holidays: set[date]) -> bool:
    if d.weekday() in [5,6]:
        return False
    elif d in holidays:
        return False
    else:
        return True

# Returns the nth working day after start. The start day itself is never counted,
# which also handles requests received on a weekend or bank holiday.
def add_working_days(start: date, n: int, holidays: set[date]) -> date :
    day = 1
    d = start
    while n > 0:
        d = start + timedelta(days=day)
        if is_working_day(d, holidays):
            n -= 1
        day+=1

    return d

# FOI Act s.10: respond within 20 working days of receipt.
# Refuses to answer when the holiday data doesn't cover the dates involved.
def foi_due_date(received: date, holidays: set[date]) -> date:
    due = add_working_days(received, 20, holidays)
    if holidays and not (min(holidays).year <= received.year and due.year <= max(holidays).year):
        raise HolidayDataOutOfRange(
            f"Bank holiday data covers {min(holidays).year} to {max(holidays).year}; "
            f"cannot calculate a due date for a request received on {received.isoformat()}"
        )
    return due


def count_working_days(after: date, up_to: date, holidays: set[date]) -> int:
    """Working days in the range (after, up_to]: the first day is excluded, the last included."""
    count = 0
    d = after + timedelta(days=1)
    while d <= up_to:
        if is_working_day(d, holidays):
            count += 1
        d += timedelta(days=1)
    return count


# Working days left until the due date: 0 on the due date, negative once overdue.
# An overdue request is always at least -1, even when today is a weekend.
def working_days_left(today: date, due: date, holidays: set[date]) -> int:
    if due >= today:
        return count_working_days(today, due, holidays)
    return -max(1, count_working_days(due, today, holidays))
