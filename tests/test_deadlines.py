from datetime import date
from app.deadlines import is_working_day

def test_weekend_is_not_a_working_day():
    assert is_working_day(date(2026, 11, 21), set()) is False