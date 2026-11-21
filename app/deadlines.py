import json
from datetime import date
from datetime import timedelta

# Loads bank holidays into bank_holidays set
def load_bank_holidays(path:str) -> set[date]:
    with open(path, mode="r", encoding="utf-8") as file:
        data = json.load(file)
        
    bank_holidays = set()
    
    for event in data["england-and-wales"]["events"]:
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

# Returns nth day from the start date    
def add_working_days(start: date, n: int, holidays: set[date]) -> date :
    day = 1
    d = start
    while n > 0:
        d = start + timedelta(days=day)
        if is_working_day(d, holidays):
            n -= 1
        day+=1
        
    return d

# Returns the due date for FOI(Freedom of Information) ticket
def foi_due_date(received: date, holidays: set[date]) -> date:
    return add_working_days(received, 20, holidays)
