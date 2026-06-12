"""Grounding validator — free (code). Every substantive number in the answer must trace
back to the computed result. The defense against hallucinated figures.

Lenient by design: matches under rounding and fraction<->percentage scaling, and ignores
small structural integers (e.g. "2-year contract", "top 3"). Used by COMPOSE and NARRATE.
Can be swapped for a model-based grounding later if stricter checking is needed.
"""
from __future__ import annotations

import re

from src.core import Verdict

# comma-grouped numbers (1,234.5) OR plain numbers (12, 3.4)
_NUM_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


def validate_grounding(answer, result_text, level: str = "grounding") -> Verdict:
    answer_nums = _numbers(answer)
    if not answer_nums:
        return Verdict(ok=True, level=level, reason="no numeric claims")
    sources = _numbers(result_text)
    ungrounded = [n for n in answer_nums
                  if not _traceable(n, sources) and not _structural(n)]
    if ungrounded:
        return Verdict(ok=False, level=level,
                       reason=f"ungrounded number(s) not in result: {ungrounded}")
    return Verdict(ok=True, level=level)


def _numbers(text):
    nums = []
    for tok in _NUM_RE.findall(text or ""):
        try:
            nums.append(float(tok.replace(",", "")))
        except ValueError:
            pass
    return nums


def _traceable(n, sources, tol: float = 0.02) -> bool:
    """True if n matches a source value (also trying x100 / /100 for percentages)."""
    for s in sources:
        for cand in (s, s * 100.0, s / 100.0):
            if abs(n - cand) <= tol * max(abs(cand), 1.0) + 1e-9:
                return True
    return False


def _structural(n) -> bool:
    """Small whole numbers are usually structural ("2-year", "top 3"), not claims."""
    return float(n).is_integer() and abs(n) < 10
