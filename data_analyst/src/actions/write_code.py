"""WRITE_CODE [agent] — write ONE pandas/matplotlib cell from the plan.

System prompt: prompts/actions/write_code.md. The USER message is built here from the
profile + question + plan. Output is a code string (not JSON). Validated at the syntax
level: it must parse AND import only allowed packages (the import allowlist).
"""
from __future__ import annotations

import json

from src.actions.base import agent_run, extract_code
from src.prompts import load_prompt
from src.validators.syntax import validate_code

NAME = "WRITE_CODE"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    plan = ctx.data.get("plan") if getattr(ctx, "data", None) else None
    plan_block = json.dumps(plan, indent=2) if plan else "(no plan; infer from the question)"
    user = f"PROFILE:\n{profile_block}\n\nQUESTION:\n{ctx.question}\n\nPLAN:\n{plan_block}"
    return [
        {"role": "system", "content": load_prompt("actions/write_code")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return extract_code(raw)


def run(state, ctx):
    return agent_run(NAME, build_messages, parse, state, ctx,
                     model_tier=MODEL_TIER, json_mode=False)


def validate(output, ctx):
    return validate_code(output)


if __name__ == "__main__":
    from types import SimpleNamespace

    from src.actions import plan_step
    from src.logging_setup import setup_logging
    from src.models import get_models
    from src.profiler import DEFAULT_CSV, profile_csv
    from src.sandbox import Sandbox

    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    models = get_models()
    sb = Sandbox()
    state = SimpleNamespace(tier="cheap")

    questions = [
        "What is the average total charges overall?",         # the TotalCharges gotcha
        "Show churn count by contract type as a bar chart.",  # produces an artifact
    ]
    for q in questions:
        ctx = SimpleNamespace(profile=profile, question=q, models=models, path="chat", data={})
        ctx.data["plan"] = plan_step.run(state, ctx)
        code = run(state, ctx)
        v = validate(code, ctx)
        print(f"\n=== {q} ===")
        print("--- code ---\n" + code)
        print(f"syntax valid: {v.ok}  {v.reason}")
        res = sb.exec(code)
        print("stdout   :", (res.stdout or "")[:200])
        print("error    :", res.error.splitlines()[-1] if res.error else "(none)")
        print("artifacts:", res.artifacts or "(none)")

    # import-allowlist demonstration
    bad = validate("import os\nprint(os.listdir('.'))", None)
    print(f"\n[validator] 'import os' -> ok={bad.ok}  reason: {bad.reason}")
