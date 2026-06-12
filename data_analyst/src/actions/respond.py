"""RESPOND [agent] — short out-of-scope reply. System prompt: prompts/actions/respond.md.

No validation rung (the reply is free prose); the transition routes straight to DONE.
"""
from __future__ import annotations

from src.actions.base import agent_run
from src.core import Verdict
from src.prompts import load_prompt

NAME = "RESPOND"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    user = f"PROFILE:\n{profile_block}\n\nMESSAGE:\n{ctx.question}"
    return [
        {"role": "system", "content": load_prompt("actions/respond")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return raw.strip()


def run(state, ctx):
    text = agent_run(NAME, build_messages, parse, state, ctx, model_tier=MODEL_TIER, json_mode=False)
    if getattr(ctx, "data", None) is not None:
        ctx.data["answer"] = text
    return text


def validate(output, ctx):
    return Verdict(ok=True, level="none")
