"""ASK [agent] — ask ONE clarifying question. System prompt: prompts/actions/ask.md.

Emits a question for the user; the transition routes to AWAIT (the turn ends, the next
user message resumes at CLASSIFY). Validated at the schema level (non-empty question).
"""
from __future__ import annotations

from src.actions.base import agent_run
from src.core import Verdict
from src.prompts import load_prompt

NAME = "ASK"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    user = f"PROFILE:\n{profile_block}\n\nMESSAGE:\n{ctx.question}"
    return [
        {"role": "system", "content": load_prompt("actions/ask")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return raw.strip()


def run(state, ctx):
    q = agent_run(NAME, build_messages, parse, state, ctx, model_tier=MODEL_TIER, json_mode=False)
    if getattr(ctx, "data", None) is not None:
        ctx.data["answer"] = q
    return q


def validate(output, ctx):
    ok = isinstance(output, str) and bool(output.strip())
    return Verdict(ok=ok, level="schema", reason="" if ok else "empty question")
