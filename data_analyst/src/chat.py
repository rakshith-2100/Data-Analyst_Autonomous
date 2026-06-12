"""chat.py — drive one chat turn through the state machine (the full chat path).

answer(question) builds a Ctx, starts at CLASSIFY, and runs run_machine until terminal
(DONE / AWAIT / FAIL). Returns the final State + the Ctx (whose data['answer'] holds the
delivered text).
"""
from __future__ import annotations

import asyncio

from src.core import State
from src.logging_setup import setup_logging
from src.models import get_models
from src.orchestrator import Ctx, run_machine
from src.profiler import DEFAULT_CSV, profile_csv
from src.sandbox import Sandbox


def answer(question, *, profile, sandbox, models, trace_path=""):
    ctx = Ctx(path="chat", profile=profile, question=question,
              sandbox=sandbox, models=models, trace_path=trace_path)
    end = asyncio.run(run_machine(State(name="CLASSIFY"), ctx))
    return end, ctx


if __name__ == "__main__":
    setup_logging()
    profile = profile_csv(DEFAULT_CSV)
    models = get_models()
    sandbox = Sandbox()

    questions = [
        "What is the average monthly charge for churned customers?",
        "Which contract type has the highest churn rate?",
        "tell me about the data",            # -> unclear -> ASK -> AWAIT
        "what's the capital of France?",     # -> out_of_scope -> RESPOND
    ]
    for q in questions:
        end, ctx = answer(q, profile=profile, sandbox=sandbox, models=models)
        out = ctx.data.get("answer") or end.data.get("reason", "(none)")
        print(f"\nQ: {q}\n  final state: {end.name}\n  -> {out}")
