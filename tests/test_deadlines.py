from datetime import date
from pathlib import Path
from app.deadlines import is_working_day
from app.deadlines import foi_due_date
from app.deadlines import load_bank_holidays
from app.deadlines import working_days_left
from app.deadlines import HolidayDataOutOfRange
import pytest

HOLIDAYS_PATH = Path(__file__).parent.parent / "data" / "bank-holidays.json"

def test_weekend_is_not_a_working_day():
    assert is_working_day(date(2026, 11, 21), set()) is False
    
def test_christmas_day_is_not_a_working_day():
    assert is_working_day(date(2026, 12, 25), load_bank_holidays(HOLIDAYS_PATH)) is False
    
def test_received_friday_counts_from_monday():
    assert foi_due_date(date(2026, 11, 6), set()) == date(2026, 12, 4)
    
def test_normal_month_no_holidays(): 
    assert foi_due_date(date(2026, 11, 2), set()) == date(2026, 11, 30)
    
def test_skips_christmas_boxing_day_and_new_year():
    assert foi_due_date(date(2026, 12, 7), load_bank_holidays(HOLIDAYS_PATH)) == date(2027, 1, 8)  # also skips Scotland's 2 January holiday, moved to Mon 4 Jan
    
def test_skips_good_friday_and_easter_monday():
    assert foi_due_date(date(2027, 3, 15), load_bank_holidays(HOLIDAYS_PATH)) == date(2027, 4, 15)  # also skips St Patrick's Day, 17 March

# ICO s.10 guidance: received on a non-working day, the clock starts on the next working day
def test_received_on_weekend():
    assert foi_due_date(date(2026, 11, 21), load_bank_holidays(HOLIDAYS_PATH)) == date(2026, 12, 21)  # also skips St Andrew's Day, 30 November


# FOIA s.10(6): a bank holiday in any part of the UK is a non-working day everywhere
def test_counts_bank_holidays_in_any_part_of_the_uk():
    assert foi_due_date(date(2026, 11, 2), load_bank_holidays(HOLIDAYS_PATH)) == date(2026, 12, 1)

def test_due_date_beyond_holiday_data_is_refused():
    with pytest.raises(HolidayDataOutOfRange):
        foi_due_date(date(2028, 12, 20), load_bank_holidays(HOLIDAYS_PATH))

def test_working_days_left_is_zero_on_the_due_date():
    assert working_days_left(date(2026, 11, 30), date(2026, 11, 30), set()) == 0

def test_working_days_left_skips_the_weekend():
    # Friday to the following Monday is one working day
    assert working_days_left(date(2026, 11, 27), date(2026, 11, 30), set()) == 1

def test_overdue_on_a_weekend_is_still_negative():
    # Due Friday, today Saturday: no working day has passed, but it is overdue
    assert working_days_left(date(2026, 11, 28), date(2026, 11, 27), set()) == -1
