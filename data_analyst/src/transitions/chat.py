"""Chat path transition table. Each fn: (verdict, state, output) -> next State.

Reads the verdict + named counters and returns the next State. Never validates, never does
work. Mirrors the deepened table in docs/TRANSITION_TABLE.md.
"""
from __future__ import annotations

from src.transitions.util import bump, count, goto, reset

REPAIR_CAP = 3  # N — the repair retry cap


def from_classify(verdict, state, output):
    label = output.get("label") if isinstance(output, dict) else None
    if not verdict.ok or label is None:
        return goto("ASK", state)
    return {
        "question": goto("PLAN_STEP", state),
        "unclear": goto("ASK", state),
        "refine": goto("RESPOND", state),       # report path not wired yet (Stage: report)
        "out_of_scope": goto("RESPOND", state),
    }.get(label, goto("ASK", state))


def from_plan_step(verdict, state, output):
    if verdict.ok:
        return goto("WRITE_CODE", state, counters=reset(state, "code"))
    if count(state, "plan") < 2:
        return goto("PLAN_STEP", state, counters=bump(state, "plan"))
    return goto("ASK", state)                    # can't resolve columns -> ask the user


def from_write_code(verdict, state, output):
    if verdict.ok:
        return goto("EXECUTE", state)
    if count(state, "code") < 2:
        return goto("WRITE_CODE", state, counters=bump(state, "code"))
    return goto("ESCALATE", state)


def from_execute(verdict, state, output):
    if verdict.ok:
        return goto("CHECK", state, counters=reset(state, "repair", "reduce"))
    data = dict(state.data)
    sig = verdict.signature
    if sig and sig == data.get("last_sig"):       # same error twice -> feedback didn't land
        return goto("ESCALATE", state, data=data)
    data["last_sig"] = sig
    if verdict.error_kind == "RESOURCE" and count(state, "reduce") < 2:
        return goto("REDUCE", state, data=data, counters=bump(state, "reduce"))
    if count(state, "repair") < REPAIR_CAP:
        return goto("ENRICH", state, data=data, counters=bump(state, "repair"))
    return goto("ESCALATE", state, data=data)


def from_enrich(verdict, state, output):
    return goto("REPAIR", state)


def from_repair(verdict, state, output):
    if verdict.ok:
        return goto("EXECUTE", state)
    if count(state, "code") < 2:
        return goto("REPAIR", state, counters=bump(state, "code"))
    return goto("ESCALATE", state)


def from_reduce(verdict, state, output):
    if verdict.ok:
        return goto("EXECUTE", state)
    return goto("ESCALATE", state)


def from_check(verdict, state, output):
    if verdict.ok:
        return goto("COMPOSE", state, counters=reset(state, "compose"))
    if count(state, "check") < 2:
        c = bump(state, "check")
        c.pop("plan", None)
        c.pop("code", None)                       # fresh plan attempt
        return goto("PLAN_STEP", state, counters=c)
    return goto("ESCALATE", state)


def from_compose(verdict, state, output):
    if verdict.ok:
        return goto("DELIVER", state)
    if count(state, "compose") < 2:
        return goto("COMPOSE", state, counters=bump(state, "compose"))
    return goto("FAIL", state, data={**state.data, "reason": "could not produce a grounded answer"})


def from_ask(verdict, state, output):
    return goto("AWAIT", state)


def from_respond(verdict, state, output):
    return goto("DONE", state)


def from_escalate(verdict, state, output):
    if state.esc_level == 0:                       # rung 1: change strategy
        return goto("PLAN_STEP", state, esc_level=1,
                    counters=reset(state, "code", "repair", "reduce"))
    if state.esc_level == 1:                       # rung 2: stronger model, same plan
        return goto("WRITE_CODE", state, esc_level=2, tier="strong",
                    counters=reset(state, "code", "repair"))
    return goto("FAIL", state, data={**state.data, "reason": "exhausted recovery options"})


def from_deliver(verdict, state, output):
    return goto("DONE", state)


def from_fail(verdict, state, output):
    return goto("DONE", state)


TABLE = {
    "CLASSIFY": from_classify,
    "PLAN_STEP": from_plan_step,
    "WRITE_CODE": from_write_code,
    "EXECUTE": from_execute,
    "ENRICH": from_enrich,
    "REPAIR": from_repair,
    "REDUCE": from_reduce,
    "CHECK": from_check,
    "COMPOSE": from_compose,
    "ASK": from_ask,
    "RESPOND": from_respond,
    "ESCALATE": from_escalate,
    "DELIVER": from_deliver,
    "FAIL": from_fail,
}
