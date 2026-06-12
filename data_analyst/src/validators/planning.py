"""Planning validator — free. Checks every referenced column exists in the profile.

Catches the most common silent failure: the model misremembering a column's name or
casing. Used by PLAN_STEP, PLAN_REPORT, and REDUCE.
"""
from __future__ import annotations

from src.core import Verdict


def validate_columns(output, profile, level: str = "planning") -> Verdict:
    """Verify output['columns'] is a list of names that all exist in the profile."""
    if not isinstance(output, dict) or "columns" not in output:
        return Verdict(ok=False, level=level, reason="missing 'columns'")
    cols = output.get("columns")
    if not isinstance(cols, list):
        return Verdict(ok=False, level=level, reason="'columns' must be a list")
    known = set(profile.column_names)
    bad = [c for c in cols if c not in known]
    if bad:
        return Verdict(ok=False, level=level, reason=f"unknown columns {bad}")
    return Verdict(ok=True, level=level)
