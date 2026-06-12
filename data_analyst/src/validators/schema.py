"""Schema validator — the cheapest level. Checks output is the expected JSON shape / enum.

Free (no model). Used by actions whose failure mode is "the model returned the wrong
shape or an out-of-set value" (CLASSIFY, ASK, ...).
"""
from __future__ import annotations

from src.core import Verdict


def validate_enum(output, field: str, allowed, level: str = "schema") -> Verdict:
    """Verify output is a dict with `field` present and its value in `allowed`."""
    if not isinstance(output, dict):
        return Verdict(ok=False, level=level,
                       reason=f"expected JSON object, got {type(output).__name__}")
    if field not in output:
        return Verdict(ok=False, level=level, reason=f"missing field '{field}'")
    value = output[field]
    if value not in allowed:
        return Verdict(ok=False, level=level,
                       reason=f"{field}={value!r} not in {sorted(allowed)}")
    return Verdict(ok=True, level=level)
