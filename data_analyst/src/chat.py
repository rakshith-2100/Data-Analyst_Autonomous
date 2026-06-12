"""chat.py — drive chat turns through the state machine.

ChatSession adds two things on top of run_machine:

  * conversation memory — a short rolling history fed into each turn (so "now as a pie"
    works);
  * AWAIT resume — when a turn ends at AWAIT (the agent asked a clarifying question), the
    next user message is folded back into the original question and re-run, so the
    clarify -> answer loop closes across turns.

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
    """One conversation: profile + sandbox + models + rolling history + pending clarification."""

    def __init__(self, profile, sandbox, models, *, max_turns: int = 4, trace_path: str = ""):
        self.profile = profile
        self.sandbox = sandbox
        self.models = models
        self.max_turns = max_turns
        self.trace_path = trace_path
        self.history: list[dict] = []
        # set while awaiting a clarification: {"original", "trail", "clarify_q"}
        self.pending: dict | None = None

    def summary(self) -> str:
        turns = self.history[-self.max_turns:]
        return "\n".join(f"User: {t['q']}\nAssistant: {t['a']}" for t in turns)

    def _last_code(self) -> str:
        for t in reversed(self.history):
            if t.get("code"):
                return t["code"]
        return ""

    def _question_for(self, message: str):
        """Return (machine_question, original, trail). If awaiting a clarification, fold the
        reply back into the original request; otherwise the message is the question."""
        if not self.pending:
            return message, message, []
        original = self.pending["original"]
        trail = self.pending["trail"] + [(self.pending["clarify_q"], message)]
        clar = "\n".join(f'- you asked "{q}" -> user answered "{a}"' for q, a in trail)
        question = (f"{original}\n\nClarifications:\n{clar}\n\n"
                    f"Now answer the original request using these clarifications.")
        return question, original, trail

    def ask(self, message):
        question, original, trail = self._question_for(message)

        ctx = Ctx(path="chat", profile=self.profile, question=question,
                  sandbox=self.sandbox, models=self.models,
                  summary=self.summary(), trace_path=self.trace_path)
        ctx.data["prev_code"] = self._last_code()
        end = asyncio.run(run_machine(State(name="CLASSIFY"), ctx))
        ans = ctx.data.get("answer") or end.data.get("reason", "")

        if end.name == "AWAIT":
            # the agent asked a (further) clarifying question — keep accumulating
            self.pending = {"original": original, "trail": trail, "clarify_q": ans}
        else:
            self.pending = None

        self.history.append({"q": message, "a": ans, "code": ctx.data.get("code", "")})
        return end, ctx


def answer(question, *, profile, sandbox, models, trace_path=""):
    """A single stateless turn (no memory, no AWAIT resume)."""
    ctx = Ctx(path="chat", profile=profile, question=question,
              sandbox=sandbox, models=models, trace_path=trace_path)
    end = asyncio.run(run_machine(State(name="CLASSIFY"), ctx))
    return end, ctx


if __name__ == "__main__":
    from pathlib import Path

    setup_logging()
    session = ChatSession(profile_csv(DEFAULT_CSV), Sandbox(), get_models())

    turns = [
        "tell me about the data",                                  # vague -> ASK (AWAIT)
        "the average monthly charge for churned vs retained",       # clarification -> resume -> answer
        "now show it as a bar chart",                               # follow-up
    ]
    for q in turns:
        end, ctx = session.ask(q)
        arts = ctx.data.get("exec_result").artifacts if ctx.data.get("exec_result") else []
        print(f"\nUSER  : {q}\n  state : {end.name}\n  reply : {ctx.data.get('answer')}"
              f"\n  charts: {[Path(a).name for a in arts]}")
