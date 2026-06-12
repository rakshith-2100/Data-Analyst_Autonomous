"""Report path transition table.

Each fn: (verdict, state, output) -> next State. Stubs return None for now.
"""


def from_plan_report(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_refine_report(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_dispatch(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_narrate(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


def from_assemble(verdict, state, output):
    """TODO — read the verdict, return the next State."""
    return None


TABLE = {
    "PLAN_REPORT": from_plan_report,
    "REFINE_REPORT": from_refine_report,
    "DISPATCH": from_dispatch,
    "NARRATE": from_narrate,
    "ASSEMBLE": from_assemble,
}
