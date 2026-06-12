"""chat.py — drive chat turns through the state machine.

ChatSession adds conversation memory: it keeps a short rolling history and feeds the
conversation summary (+ the previous code) into each turn, so follow-ups like "now show it
as a pie" are understood. The sandbox is shared across turns but stateless per exec — the
model recomputes from df, guided by the previous code (a persistent namespace is a later,
optional step).

answer() is a single stateless turn (used by isolated tests).
"""
from __future__ import annotations

import asyncio

from src.core import State
from src.logging_setup import setup_logging
from src.models import get_models
from src.orchestrator import Ctx, run_machine
from src.profiler import DEFAULT_CSV, profile_csv
from src.sandbox import Sandbox


class ChatSession:
    """One conversation: profile + sandbox + models + rolling history."""

    def __init__(self, profile, sandbox, models, *, max_turns: int = 4, trace_path: str = ""):
        self.profile = profile
        self.sandbox = sandbox
        self.models = models
        self.max_turns = max_turns
        self.trace_path = trace_path
        self.history: list[dict] = []

    def summary(self) -> str:
        turns = self.history[-self.max_turns:]
        return "\n".join(f"User: {t['q']}\nAssistant: {t['a']}" for t in turns)

    def _last_code(self) -> str:
        for t in reversed(self.history):
            if t.get("code"):
                return t["code"]
        return ""

    def ask(self, question):
        ctx = Ctx(path="chat", profile=self.profile, question=question,
                  sandbox=self.sandbox, models=self.models,
                  summary=self.summary(), trace_path=self.trace_path)
        ctx.data["prev_code"] = self._last_code()
        end = asyncio.run(run_machine(State(name="CLASSIFY"), ctx))
        ans = ctx.data.get("answer") or end.data.get("reason", "")
        self.history.append({"q": question, "a": ans, "code": ctx.data.get("code", "")})
        return end, ctx


def answer(question, *, profile, sandbox, models, trace_path=""):
    """A single stateless turn (no memory)."""
    ctx = Ctx(path="chat", profile=profile, question=question,
              sandbox=sandbox, models=models, trace_path=trace_path)
    end = asyncio.run(run_machine(State(name="CLASSIFY"), ctx))
    return end, ctx


if __name__ == "__main__":
    from pathlib import Path

    setup_logging()
    session = ChatSession(profile_csv(DEFAULT_CSV), Sandbox(), get_models())

    turns = [
        "Show churn count by contract type as a bar chart.",
        "now show it as a pie chart of the totals per contract",   # follow-up
        "and what is the churn rate for month-to-month customers?",  # new question
    ]
    for q in turns:
        end, ctx = session.ask(q)
        arts = ctx.data.get("exec_result").artifacts if ctx.data.get("exec_result") else []
        print(f"\nQ: {q}\n  state : {end.name}\n  answer: {ctx.data.get('answer')}"
              f"\n  charts: {[Path(a).name for a in arts]}")
