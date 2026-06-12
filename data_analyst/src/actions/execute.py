"""EXECUTE [sys] — run the current code cell in the sandbox -> ExecResult. No model.

Reads ctx.data['code'], runs it in ctx.sandbox, stashes the result for the downstream
ENRICH / REPAIR / CHECK actions, and returns the ExecResult. Validated at the runtime
level (classify -> clean | error_kind | signature).
"""
from __future__ import annotations

from src.validators.runtime import classify

NAME = "EXECUTE"


def run(state, ctx):
    code = ctx.data.get("code", "")
    result = ctx.sandbox.exec(code)
    ctx.data["exec_result"] = result
    return result


def validate(output, ctx):
    return classify(output)
