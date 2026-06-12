"""COMPOSE [agent] — write the final answer over the computed result.

System prompt: prompts/actions/compose.md. The USER message is built here from the
question + result stdout + chart path. Output is plain prose. Validated at the grounding
level: every substantive number in the answer must trace back to the result (free, code).
"""
from __future__ import annotations

from src.actions.base import agent_run
from src.prompts import load_prompt
from src.validators.grounding import validate_grounding

NAME = "COMPOSE"
MODEL_TIER = "cheap"


def build_messages(ctx):
    result = ctx.data.get("exec_result")
    stdout = result.stdout if result and result.stdout else "(no result)"
    charts = result.artifacts if result else []
    chart_line = f"\n\nCHART: {charts[0]}" if charts else ""
    user = f"QUESTION:\n{ctx.question}\n\nRESULT:\n{stdout}{chart_line}"
    return [
        {"role": "system", "content": load_prompt("actions/compose")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return raw.strip()


def run(state, ctx):
    answer = agent_run(NAME, build_messages, parse, state, ctx,
                       model_tier=MODEL_TIER, json_mode=False)
    if getattr(ctx, "data", None) is not None:
        ctx.data["answer"] = answer  # DELIVER presents this
    return answer


def validate(output, ctx):
    result = ctx.data.get("exec_result")
    source = result.stdout if result else ""
    return validate_grounding(output, source)


if __name__ == "__main__":
    from types import SimpleNamespace

    from src.actions import execute, plan_step, write_code
    from src.logging_setup import setup_logging
    from src.models import get_models
    from src.profiler import DEFAULT_CSV, profile_csv
    from src.sandbox import Sandbox
    from src.validators.grounding import validate_grounding

    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    models = get_models()
    state = SimpleNamespace(tier="cheap")

    # 1) full chain -> grounded answer
    q = "What is the average total charges for churned customers?"
    ctx = SimpleNamespace(profile=profile, question=q, models=models,
                          sandbox=Sandbox(), path="chat", data={})
    ctx.data["plan"] = plan_step.run(state, ctx)
    write_code.run(state, ctx)
    execute.run(state, ctx)
    answer = run(state, ctx)
    v = validate(answer, ctx)
    print(f"\n[full chain] Q: {q}")
    print("RESULT :", ctx.data["exec_result"].stdout)
    print("ANSWER :", answer)
    print(f"grounding -> ok={v.ok}  {v.reason}")

    # 2) hallucination: an answer with a number that is NOT in the result
    fake = "The average total charge for churned customers is 9876.54 dollars."
    fv = validate_grounding(fake, ctx.data["exec_result"].stdout)
    print(f"\n[hallucination] fabricated: {fake}")
    print(f"result was: {ctx.data['exec_result'].stdout}")
    print(f"grounding -> ok={fv.ok}  {fv.reason}  (expect False)")
