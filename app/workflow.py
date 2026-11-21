from enum import Enum

class Status(str, Enum):
    RECEIVED = "RECEIVED"
    IN_PROGRESS = "IN_PROGRESS"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"
    
# Single source of truth for the status lifecycle. CLOSED and WITHDRAWN are final.
# main.render_detail also reads it to decide which buttons the detail page shows.
ALLOWED_TRANSITIONS = {
    Status.RECEIVED: {Status.IN_PROGRESS, Status.WITHDRAWN},
    Status.IN_PROGRESS: {Status.RESPONDED, Status.WITHDRAWN},
    Status.RESPONDED: {Status.CLOSED},
    Status.CLOSED: set(),
    Status.WITHDRAWN: set()
}

# Carries the allowed moves so the API can tell the client what it could have done instead.
class InvalidTransition(Exception):
    def __init__(self,current,target):
        self.current = current
        self.target = target
        self.allowed = ALLOWED_TRANSITIONS[current]
        
        super().__init__(f"Cannot transition from {self.current.value} to {self.target.value}")
        
class RequestNotFound(Exception):
    def __init__(self, request_id):
        self.request_id = request_id
        
        super().__init__(f"Request {self.request_id} not found")

def check_transition(current: Status, target: Status) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(current, target)
