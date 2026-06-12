"""ESCALATE [sys] — no-op action; the recovery ladder lives in transitions/chat.py.

The action does nothing. The transition reads state.esc_level and picks the next rung
(restrategize -> stronger model -> bail). It is kept as a real state so the ladder is
explicit and shows up in the trace.
"""
from __future__ import annotations

from src.core import Verdict

NAME = "ESCALATE"


def run(state, ctx):
    return None


def validate(output, ctx):
    return Verdict(ok=True, level="escalate")
