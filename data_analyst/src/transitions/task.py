"""Per-task sub-machine transition table (DISPATCH fan-out, stateless).

Each fn: (verdict, state, output) -> next State. Stubs return None for now.
"""


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


TABLE = {
    "WRITE_CODE": from_write_code,
    "EXECUTE": from_execute,
    "ENRICH": from_enrich,
    "REPAIR": from_repair,
    "REDUCE": from_reduce,
    "CHECK": from_check,
}
