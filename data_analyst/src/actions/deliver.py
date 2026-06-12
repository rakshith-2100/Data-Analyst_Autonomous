"""DELIVER [sys] — present the final answer + chart artifacts. No model.

Reads ctx.data['answer'] (set by COMPOSE/RESPOND/ASK) and any chart artifacts, logs them,
and returns the answer. The transition routes to DONE.
"""
from __future__ import annotations

from src.core import Verdict
from src.logging_setup import agentic, generic

NAME = "DELIVER"


def run(state, ctx):
    answer = ctx.data.get("answer", "")
    result = ctx.data.get("exec_result")
    artifacts = result.artifacts if result else []
    generic().info("DELIVER: %s", (answer or "").replace("\n", " ")[:120])
    agentic().info("DELIVER\n%s\nartifacts: %s", answer or "(no answer)", artifacts or "(none)")
    return answer


def validate(output, ctx):
    return Verdict(ok=True, level="deliver")
