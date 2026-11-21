from enum import Enum

class Status(str, Enum):
    RECEIVED = "RECEIVED"
    IN_PROGRESS = "IN_PROGRESS"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"
    
ALLOWED_TRANSITIONS = {
    Status.RECEIVED: {Status.IN_PROGRESS, Status.WITHDRAWN},
    Status.IN_PROGRESS: {Status.RESPONDED, Status.WITHDRAWN},
    Status.RESPONDED: {Status.CLOSED},
    Status.CLOSED: set(),
    Status.WITHDRAWN: set()
}

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
