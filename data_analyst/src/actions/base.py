"""Shared helpers for [agent] actions.

`agent_run` is the single adapter every [agent] action uses: pick the tier, call the one
model client (Models.complete), parse the reply. Besides models.py, this is the only
place that touches a model call — actions just supply build_messages + parse.
"""
from __future__ import annotations

import json
import re


def agent_run(action_name: str, build_messages, parse, state, ctx, *,
              model_tier: str = "cheap", json_mode: bool = False):
    """build_messages -> model call (tier from state/MODEL_TIER) -> parse -> output."""
    tier = "strong" if getattr(state, "tier", "cheap") == "strong" else model_tier
    messages = build_messages(ctx)
    raw = ctx.models.complete(messages, tier=tier, action=action_name.lower(), json_mode=json_mode)
    return parse(raw)


def strip_fences(text: str) -> str:
    """Drop a leading ```lang fence and trailing ``` if the model added them."""
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def parse_json(raw: str) -> dict:
    """Parse a JSON object from a model reply (tolerates stray code fences)."""
    return json.loads(strip_fences(raw))
