import json
from datetime import date

source = "data/bank-holidays.json"
    
def load_bank_holidays(path:str) -> set[date]:
    with open(path, mode="r", encoding="utf-8") as file:
        data = json.load(file)
        
    bank_holidays = set()
    
    for event in data["england-and-wales"]["events"]:
        bank_holidays.add(date.fromisoformat(event["date"]))
            
    return bank_holidays   
        

def is_working_day(d: date, holidays: set[date]) -> bool:
    if d.weekday() in [5,6]:
        return False
    elif d in holidays:
        return False
    else:
        return True
    
def add_working_days(start: date, n: int, holidays: set[date]) -> date :
    while n > 0:
        d = start + timedelta(days=1)
        if is_working_day(d):
            n -= 1
        
    return d
