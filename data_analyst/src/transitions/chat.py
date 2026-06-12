"""Chat path transition table.

Each fn: (verdict, state, output) -> next State. Stubs return None for now.
"""


def from_classify(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_plan_step(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_write_code(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_execute(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_enrich(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_repair(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_reduce(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_check(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_compose(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_ask(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_respond(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_escalate(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_deliver(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_fail(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


TABLE = {
    "CLASSIFY": from_classify,
    "PLAN_STEP": from_plan_step,
    "WRITE_CODE": from_write_code,
    "EXECUTE": from_execute,
    "ENRICH": from_enrich,
    "REPAIR": from_repair,
    "REDUCE": from_reduce,
    "CHECK": from_check,
    "COMPOSE": from_compose,
    "ASK": from_ask,
    "RESPOND": from_respond,
    "ESCALATE": from_escalate,
    "DELIVER": from_deliver,
    "FAIL": from_fail,
}
