"""orchestrator.py — the generic state-machine engine. See docs/ORCHESTRATOR.md.

Drives one loop: state -> action.run -> action.validate -> transition -> trace, until a
terminal state. Domain-blind — it knows no state name except the TERMINAL set; all
churn/chart/report logic lives in actions/, validators/, transitions/.

Phase 4: implement run_machine + trace. Stub for now (returns None).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.actions import ACTIONS          # noqa: F401  (used once run_machine is implemented)
from src.transitions import TRANSITIONS  # noqa: F401

TERMINAL = {"DONE", "FAIL", "AWAIT"}      # AWAIT = ASK emitted a question; hand back to user


@dataclass
class Ctx:
    """Assembled once per run — the only object actions/validators/transitions receive."""
    path: str                       # "chat" | "report" | "task" -> selects the transition table
    profile: object = None          # src.schemas.Profile
    question: str = ""              # or task.instruction in the report/task paths
    sandbox: object = None          # src.sandbox.Sandbox (persistent in chat, fresh per task)
    models: object = None           # src.models.Models
    summary: str = ""              # rolling chat summary — never the full history
    trace_path: str = ""           # traces/<session>.jsonl
    data: dict = field(default_factory=dict)


def terminal(state) -> bool:
    return state.name in TERMINAL


async def run_machine(state, ctx: Ctx, max_hops: int = 40):
    """Drive the transition table until terminal. Stub — returns None until Phase 4."""
    return None


def trace(ctx: Ctx, state, action_name: str, verdict, output) -> None:
    """Append one (state, action, verdict) line to the session trace. Stub — Phase 4/8."""
    return None
