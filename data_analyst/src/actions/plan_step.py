"""PLAN_STEP [agent] — pick columns + operation and a one-line plan (no code).

System prompt: prompts/actions/plan_step.md. The USER message is built here from the
profile + question. Validated at the planning level: every chosen column must exist in
the profile (the guard against the model misremembering column names).
"""
from __future__ import annotations

from src.actions.base import agent_run, parse_json
from src.prompts import load_prompt
from src.validators.planning import validate_columns

NAME = "PLAN_STEP"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    user = f"PROFILE:\n{profile_block}\n\nQUESTION:\n{ctx.question}"
    return [
        {"role": "system", "content": load_prompt("actions/plan_step")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return parse_json(raw)


def run(state, ctx):
    return agent_run(NAME, build_messages, parse, state, ctx,
                     model_tier=MODEL_TIER, json_mode=True)


def validate(output, ctx):
    return validate_columns(output, ctx.profile)


if __name__ == "__main__":
    from types import SimpleNamespace

    from src.logging_setup import setup_logging
    from src.models import get_models
    from src.profiler import DEFAULT_CSV, profile_csv

    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    models = get_models()
    state = SimpleNamespace(tier="cheap")

    tests = [
        "What is the average monthly charge for churned vs non-churned customers?",
        "churn rate by contract type",
        "average total charges overall",
        "which payment method has the highest churn?",
    ]
    for q in tests:
        ctx = SimpleNamespace(profile=profile, question=q, models=models, path="chat")
        out = run(state, ctx)
        v = validate(out, ctx)
        flag = "ok" if v.ok else f"INVALID ({v.reason})"
        print(f"\nQ   : {q}\nCOLS: {out.get('columns')}  [{flag}]\nOP  : {out.get('operation')}"
              f"\nPLAN: {out.get('plan')}")

    # demonstrate the planning validator catching a bad column
    bad = {"columns": ["MonthlyCharges", "NotARealColumn"], "operation": "mean", "plan": "x"}
    bv = validate(bad, SimpleNamespace(profile=profile))
    print(f"\n[validator check] bad-column plan -> ok={bv.ok}  reason: {bv.reason}")
