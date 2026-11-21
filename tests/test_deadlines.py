from datetime import date
from pathlib import Path
from app.deadlines import is_working_day
from app.deadlines import foi_due_date
from app.deadlines import load_bank_holidays

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
    assert foi_due_date(date(2026, 12, 7), load_bank_holidays(HOLIDAYS_PATH)) == date(2027, 1, 7)
    
def test_skips_good_friday_and_easter_monday():
    assert foi_due_date(date(2027, 3, 15), load_bank_holidays(HOLIDAYS_PATH)) == date(2027, 4, 14)

# ICO s.10 guidance: received on a non-working day, the clock starts on the next working day
def test_received_on_weekend():
    assert foi_due_date(date(2026, 11, 21), load_bank_holidays(HOLIDAYS_PATH)) == date(2026, 12, 18)
