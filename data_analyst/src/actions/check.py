"""CHECK [agent] — judge whether the result actually answers the question.

This is the one action whose JOB is validation, so it loads a VALIDATOR prompt
(prompts/validators/sanity.md). It reads question + code + result, asks the model a strict
yes/no, and CHECK.validate turns that into the sanity Verdict the transition routes on
(yes -> COMPOSE, no -> re-plan).
"""
from __future__ import annotations

from src.actions.base import agent_run, parse_json
from src.prompts import load_prompt
from src.validators.sanity import judge_verdict

NAME = "CHECK"
MODEL_TIER = "cheap"


def build_messages(ctx):
    result = ctx.data.get("exec_result")
    stdout = result.stdout if result and result.stdout else "(no output)"
    code = ctx.data.get("code", "")
    user = f"QUESTION:\n{ctx.question}\n\nCODE THAT RAN:\n{code}\n\nRESULT (stdout):\n{stdout}"
    return [
        {"role": "system", "content": load_prompt("validators/sanity")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return parse_json(raw)


def run(state, ctx):
    return agent_run(NAME, build_messages, parse, state, ctx,
                     model_tier=MODEL_TIER, json_mode=True)


def validate(output, ctx):
    return judge_verdict(output)


if __name__ == "__main__":
    from types import SimpleNamespace

    from src.actions import execute, plan_step, write_code
    from src.core import ExecResult
    from src.logging_setup import setup_logging
    from src.models import get_models
    from src.profiler import DEFAULT_CSV, profile_csv
    from src.sandbox import Sandbox

    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    models = get_models()
    state = SimpleNamespace(tier="cheap")

    # 1) cumulative real chain -> a correct result should PASS
    q = "What is the average total charges overall?"
    ctx = SimpleNamespace(profile=profile, question=q, models=models,
                          sandbox=Sandbox(), path="chat", data={})
    ctx.data["plan"] = plan_step.run(state, ctx)
    write_code.run(state, ctx)
    execute.run(state, ctx)
    j = run(state, ctx)
    v = validate(j, ctx)
    print(f"\n[correct] Q: {q}\n  result: {ctx.data['exec_result'].stdout}"
          f"\n  CHECK: {j}  -> ok={v.ok}  (expect True)")

    # 2) clean-but-WRONG -> result is overall TotalCharges, but the question asked for the
    #    average MONTHLY charge for churned customers
    ctx2 = SimpleNamespace(profile=profile, models=models, sandbox=None, path="chat", data={},
                           question="What is the average monthly charge for churned customers?")
    ctx2.data["code"] = "print(pd.to_numeric(df['TotalCharges'], errors='coerce').mean())"
    ctx2.data["exec_result"] = ExecResult(stdout="2283.30")
    j2 = run(state, ctx2)
    v2 = validate(j2, ctx2)
    print(f"\n[wrong]   Q: {ctx2.question}\n  result: 2283.30 (overall TotalCharges)"
          f"\n  CHECK: {j2}  -> ok={v2.ok}  (expect False)")
