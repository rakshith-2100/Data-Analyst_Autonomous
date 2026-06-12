"""REPAIR [agent] — fix the failed cell using the enriched context only.

System prompt: prompts/actions/repair.md. The USER message = profile + the enriched error
context from ENRICH (which already contains the failed code + targeted hints). The model
only fixes — it never re-diagnoses. The repaired code is stashed back to ctx.data['code']
so the next EXECUTE runs it. Validated at the syntax level.
"""
from __future__ import annotations

from src.actions.base import agent_run, extract_code
from src.prompts import load_prompt
from src.validators.syntax import validate_code

NAME = "REPAIR"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    enriched = ctx.data.get("enriched", "(no error context)")
    user = f"PROFILE:\n{profile_block}\n\n{enriched}"
    return [
        {"role": "system", "content": load_prompt("actions/repair")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return extract_code(raw)


def run(state, ctx):
    fixed = agent_run(NAME, build_messages, parse, state, ctx,
                      model_tier=MODEL_TIER, json_mode=False)
    ctx.data["code"] = fixed  # the next EXECUTE runs the repaired cell
    return fixed


def validate(output, ctx):
    return validate_code(output)


if __name__ == "__main__":
    # Prove the EXECUTE -> ENRICH -> REPAIR -> EXECUTE self-repair loop on the TotalCharges
    # gotcha, using a deliberately NAIVE cell (the kind a less careful model might write).
    from types import SimpleNamespace

    from src.actions import enrich, execute
    from src.logging_setup import setup_logging
    from src.models import get_models
    from src.profiler import DEFAULT_CSV, profile_csv
    from src.sandbox import Sandbox

    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    ctx = SimpleNamespace(profile=profile, question="What is the average total charges?",
                          models=get_models(), sandbox=Sandbox(), path="chat", data={})
    state = SimpleNamespace(tier="cheap")

    ctx.data["code"] = "print(df['TotalCharges'].astype(float).mean())"  # naive: raises ValueError
    print("--- attempt 1 (naive) ---\n" + ctx.data["code"])
    res = execute.run(state, ctx)
    v = execute.validate(res, ctx)
    print(f"EXECUTE -> ok={v.ok}  error_kind={v.error_kind}  | {v.reason or res.stdout}")

    print("\n--- ENRICH context handed to REPAIR ---")
    print(enrich.run(state, ctx))

    fixed = run(state, ctx)
    print("\n--- REPAIR produced ---\n" + fixed + f"\nsyntax ok: {validate(fixed, ctx).ok}")

    res2 = execute.run(state, ctx)
    v2 = execute.validate(res2, ctx)
    print(f"\n--- attempt 2 (repaired) ---\nEXECUTE -> ok={v2.ok}  | stdout: {res2.stdout}  "
          f"| error: {res2.error or '(none)'}")
