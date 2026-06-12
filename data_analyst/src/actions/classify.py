"""CLASSIFY [agent] — route a user message (question|unclear|refine|out_of_scope).

System prompt: prompts/actions/classify.md. The USER message is built here from the
profile + the message. Validated at the schema level (label must be one of four enums).
"""
from __future__ import annotations

from src.actions.base import agent_run, convo_block, parse_json
from src.prompts import load_prompt
from src.validators.schema import validate_enum

NAME = "CLASSIFY"
MODEL_TIER = "cheap"
LABELS = {"question", "unclear", "refine", "out_of_scope"}


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    user = f"PROFILE:\n{profile_block}{convo_block(ctx)}\n\nCURRENT MESSAGE:\n{ctx.question}"
    return [
        {"role": "system", "content": load_prompt("actions/classify")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return parse_json(raw)


def run(state, ctx):
    return agent_run(NAME, build_messages, parse, state, ctx,
                     model_tier=MODEL_TIER, json_mode=True)


def validate(output, ctx):
    return validate_enum(output, "label", LABELS)


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
        "What is the average monthly charge for churned customers?",
        "how many customers are on a two year contract?",
        "hello there",
        "drop the pie chart and add a forecast",
        "what's the weather in Mumbai today?",
        "tell me about the data",
    ]
    for q in tests:
        ctx = SimpleNamespace(profile=profile, question=q, models=models, path="chat")
        out = run(state, ctx)
        v = validate(out, ctx)
        flag = "ok" if v.ok else f"INVALID ({v.reason})"
        print(f"\nMSG  : {q}\nLABEL: {out.get('label'):<13} [{flag}]  reason: {out.get('reason')}")
