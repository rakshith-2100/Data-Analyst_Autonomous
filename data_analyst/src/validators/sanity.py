"""Sanity validator — interpret CHECK's judgment into a routable Verdict.

The model-based judging happens in the CHECK action (prompts/validators/sanity.md); this
turns its {"answers": bool, "reason": str} into the Verdict the transition routes on
(answers=true -> COMPOSE; false -> re-plan). Costs no extra model call — the call was CHECK.
"""
from __future__ import annotations

from src.core import Verdict


def judge_verdict(judgment, level: str = "sanity") -> Verdict:
    """{"answers": bool, "reason": str} -> Verdict at the sanity level."""
    if not isinstance(judgment, dict) or "answers" not in judgment:
        return Verdict(ok=False, level=level, reason="malformed judgment from CHECK")
    return Verdict(ok=bool(judgment["answers"]), level=level,
                   reason=str(judgment.get("reason", "")))
