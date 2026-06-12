"""REDUCE [agent] — rewrite the cell to use less data (timeout / memory).

System prompt: prompts/actions/reduce.md. A *different* fix from REPAIR: the code was
correct but too expensive, so we sample/chunk while answering the same question. Output is
code; the repaired cell is stashed to ctx.data['code']. Validated at the syntax level.
"""
from __future__ import annotations

from src.actions.base import agent_run, extract_code
from src.prompts import load_prompt
from src.validators.syntax import validate_code

NAME = "REDUCE"
MODEL_TIER = "cheap"


def build_messages(ctx):
    profile_block = ctx.profile.as_prompt() if ctx.profile else "(no profile loaded)"
    code = ctx.data.get("code", "")
    result = ctx.data.get("exec_result")
    err = result.error if result and result.error else "(resource limit hit)"
    user = f"PROFILE:\n{profile_block}\n\nRESOURCE ERROR:\n{err}\n\nCODE:\n{code}"
    return [
        {"role": "system", "content": load_prompt("actions/reduce")},
        {"role": "user", "content": user},
    ]


def parse(raw):
    return extract_code(raw)


def run(state, ctx):
    code = agent_run(NAME, build_messages, parse, state, ctx, model_tier=MODEL_TIER, json_mode=False)
    if getattr(ctx, "data", None) is not None:
        ctx.data["code"] = code
    return code


def validate(output, ctx):
    return validate_code(output)
