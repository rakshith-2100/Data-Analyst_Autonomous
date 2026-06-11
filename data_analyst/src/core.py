"""Core operational types — the things the state machine passes around.

Pure dataclasses, no logic, no internal imports (a leaf module, like schemas.py):

  Verdict    — a validator's judgment of one action's output; a transition reads it to route.
  State      — where the machine is, plus retry / escalation bookkeeping.
  ExecResult — the one result shape every sandbox run returns (clean or failed).
  Task       — one unit of report work (PLAN_REPORT emits these, DISPATCH runs them).

Kept separate from schemas.py (which describes the *dataset*) so the two concerns
don't blur. Produced by validators (Verdict), transitions (State), the sandbox
(ExecResult) and PLAN_REPORT (Task); driven by the orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Verdict:
    """What a validator returns; what a transition reads to route."""
    ok: bool
    level: str                  # schema | planning | syntax | runtime | sanity | grounding
    reason: str = ""
    error_kind: str | None = None   # runtime only: MISSING_COLUMN|BAD_VALUE|NAME_OR_LOGIC|RESOURCE|OTHER
    signature: str | None = None    # hash(error_type + "file:line") — detects "same error twice"


@dataclass
class State:
    """Where the machine is, plus its retry / escalation bookkeeping."""
    name: str
    data: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)  # named: plan/code/repair/reduce/check/compose
    esc_level: int = 0          # 0 none | 1 restrategized | 2 strong model
    tier: str = "cheap"         # cheap | strong (ESCALATE may flip to strong)


@dataclass
class ExecResult:
    """The one result shape every sandbox run returns — clean or failed."""
    stdout: str
    error: str | None = None    # enriched traceback, or None on success
    artifacts: list[str] = field(default_factory=list)  # files written to ./out/ this run


@dataclass
class Task:
    """One unit of report work — what PLAN_REPORT emits and DISPATCH runs."""
    id: str
    kind: str                   # "chart" | "stat"
    columns: list[str]
    operation: str
    instruction: str
    artifact_path: str | None = None
