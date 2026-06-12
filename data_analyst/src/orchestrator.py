"""orchestrator.py — the generic state-machine engine. See docs/ORCHESTRATOR.md.

Drives one loop: state -> action.run -> action.validate -> transition -> trace, until a
terminal state. Domain-blind — it knows no state name except the TERMINAL set; all
churn/chart/report logic lives in actions/, validators/, transitions/.

The engine reads two registries (ACTIONS, TRANSITIONS) and enforces the one global cap
(max_hops). Per-state retry caps live in transitions; the wall-clock timeout lives in the
sandbox. The engine just turns the crank.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import TYPE_CHECKING

from src.actions import ACTIONS
from src.core import State
from src.logging_setup import agentic, generic
from src.transitions import TRANSITIONS

if TYPE_CHECKING:
    from src.core import Verdict
    from src.models import Models
    from src.sandbox import Sandbox
    from src.schemas import Profile

TERMINAL = {"DONE", "FAIL", "AWAIT"}      # AWAIT = ASK emitted a question; hand back to user


@dataclass
class Ctx:
    """Assembled once per run — the only object actions/validators/transitions receive."""
    path: str                       # "chat" | "report" | "task" -> selects the transition table
    profile: "Profile | None" = None
    question: str = ""              # or task.instruction in the report/task paths
    sandbox: "Sandbox | None" = None  # persistent in chat, fresh per task in report
    models: "Models | None" = None
    summary: str = ""              # rolling chat summary — never the full history
    trace_path: str = ""           # traces/<session>.jsonl
    data: dict = field(default_factory=dict)


def terminal(state: State) -> bool:
    return state.name in TERMINAL


async def run_machine(state: State, ctx: Ctx, *, max_hops: int = 40,
                      actions: dict | None = None, transitions: dict | None = None) -> State:
    """Drive the transition table until a terminal state (or the global hop cap).

    `actions`/`transitions` default to the module registries; they are injectable only so
    the loop can be unit-tested with a fake machine.
    """
    actions = actions if actions is not None else ACTIONS
    table = (transitions if transitions is not None else TRANSITIONS)[ctx.path]

    for _ in range(max_hops):
        if terminal(state):
            return state

        action = actions[state.name]                       # actions/  (resolved by name)
        output = await _maybe_await(action.run(state, ctx))  # [agent] call OR [sys] code
        verdict = action.validate(output, ctx)             # validators/ (level per action)

        trace(ctx, state, getattr(action, "NAME", state.name), verdict, output)

        state = table[state.name](verdict, state, output)  # transitions/ (decides next)

    generic().error("run_machine hit max_hops=%d (last state before cap)", max_hops)
    return State(name="FAIL", data={**state.data, "reason": f"hit max_hops={max_hops}"})


def trace(ctx: Ctx, state: State, action_name: str, verdict: "Verdict | None", output) -> None:
    """Append one (state, action, verdict) line to the session trace — BEFORE the transition,
    so a crash in routing still leaves a record of what was being decided."""
    record = {
        "state": state.name,
        "action": action_name,
        "verdict": _to_jsonable(verdict),
        "tier": getattr(state, "tier", None),
        "counters": getattr(state, "counters", None),
        "output": _preview(output),
    }
    line = json.dumps(record, default=str)
    if ctx.trace_path:
        with open(ctx.trace_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    agentic().info("TRACE %s", line)


async def _maybe_await(value):
    """Allow action.run to be either sync ([sys]) or async ([agent])."""
    if inspect.isawaitable(value):
        return await value
    return value


def _to_jsonable(verdict):
    if verdict is None:
        return None
    return asdict(verdict) if is_dataclass(verdict) else str(verdict)


def _preview(output, limit: int = 300):
    if output is None:
        return None
    s = output if isinstance(output, str) else repr(output)
    return s if len(s) <= limit else s[:limit] + "..."


if __name__ == "__main__":
    # Smoke-test the loop mechanics with a fake 2-step machine (no real actions needed).
    import asyncio

    from src.core import Verdict
    from src.logging_setup import setup_logging

    setup_logging()

    class _FakeAction:
        def __init__(self, name):
            self.NAME = name

        def run(self, state, ctx):
            return f"ran {self.NAME}"

        def validate(self, output, ctx):
            return Verdict(ok=True, level="schema", reason=output)

    def _goto(next_name):
        return lambda verdict, state, output: State(name=next_name)

    fake_actions = {"PING": _FakeAction("PING"), "PONG": _FakeAction("PONG")}
    fake_trans = {"test": {"PING": _goto("PONG"), "PONG": _goto("DONE")}}

    end = asyncio.run(run_machine(
        State(name="PING"), Ctx(path="test"),
        actions=fake_actions, transitions=fake_trans,
    ))
    print("machine ended at:", end.name, "(expected DONE)")
