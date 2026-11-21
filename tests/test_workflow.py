from app.workflow import check_transition
from app.workflow import Status
from app.workflow import InvalidTransition
import pytest

def test_full_happy_path_is_allowed():
    check_transition(Status.RECEIVED, Status.IN_PROGRESS)
    check_transition(Status.IN_PROGRESS, Status.RESPONDED)
    check_transition(Status.RESPONDED, Status.CLOSED)
    
def test_cannot_close_unanswered_request():
    with pytest.raises(InvalidTransition) as exc_info:
        check_transition(Status.RECEIVED, Status.CLOSED)
    assert exc_info.value.allowed == {Status.IN_PROGRESS, Status.WITHDRAWN}

def test_cannot_move_to_same_status():
    with pytest.raises(InvalidTransition) as exc_info:
        check_transition(Status.RECEIVED, Status.RECEIVED)
    assert exc_info.value.allowed == {Status.IN_PROGRESS, Status.WITHDRAWN}

def test_final_states_have_no_moves():
    with pytest.raises(InvalidTransition) as exc_info:
        check_transition(Status.CLOSED, Status.RECEIVED)
    assert exc_info.value.allowed == set()

    with pytest.raises(InvalidTransition) as exc_info:
        check_transition(Status.WITHDRAWN, Status.RECEIVED)
    assert exc_info.value.allowed == set()