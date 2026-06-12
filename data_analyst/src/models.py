"""models.py — the OpenAI GPT client. The one place in the system that calls a model.

Two tiers, configured via .env (never hard-coded):
  OPENAI_API_KEY        — your secret key (in .env, gitignored)
  OPENAI_MODEL_CHEAP    — default for everything (e.g. gpt-4.1-mini)
  OPENAI_MODEL_STRONG   — used only on ESCALATE (e.g. gpt-4.1)

Every call logs the full prompt+response to logs/prompts_response/<action>.log and a
short line to agentic.log. Actions never touch the SDK directly — they go through
Models.complete(), so model access, tiering, and logging stay in one place.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.logging_setup import agentic, generic, log_prompt_response

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_DEFAULTS = {"cheap": "gpt-4.1-mini", "strong": "gpt-4.1"}


class Models:
    """Thin OpenAI wrapper with a cheap/strong tier and built-in logging."""

    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY not set — copy .env.example to .env and add your key."
            )
        self.client = OpenAI(api_key=key)
        self.tiers = {
            "cheap": os.environ.get("OPENAI_MODEL_CHEAP", _DEFAULTS["cheap"]),
            "strong": os.environ.get("OPENAI_MODEL_STRONG", _DEFAULTS["strong"]),
        }
        generic().info("model client ready: cheap=%s strong=%s",
                       self.tiers["cheap"], self.tiers["strong"])

    def complete(self, messages: list[dict], *, tier: str = "cheap", action: str = "model",
                 json_mode: bool = False, temperature: float = 0.0) -> str:
        """One model call. Returns the raw assistant text (actions parse it themselves)."""
        model = self.tiers.get(tier, self.tiers["cheap"])
        kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""

        log_prompt_response(action, _render(messages), text)
        agentic().info("MODEL[%s/%s] action=%s -> %s", tier, model, action,
                       text.replace("\n", " ")[:200])
        return text


_singleton: Models | None = None


def get_models() -> Models:
    """Shared Models instance (lazy — only builds the client when first needed)."""
    global _singleton
    if _singleton is None:
        _singleton = Models()
    return _singleton


def _render(messages: list[dict]) -> str:
    return "\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)


if __name__ == "__main__":
    from src.logging_setup import setup_logging

    setup_logging()
    m = get_models()
    print("cheap tier :", m.tiers["cheap"])
    print("strong tier:", m.tiers["strong"])
    out = m.complete(
        [{"role": "system",
          "content": 'You label a message about a dataset. Output ONLY JSON: '
                     '{"label": "question|out_of_scope"}.'},
         {"role": "user", "content": "What is the average tenure?"}],
        tier="cheap", action="classify", json_mode=True,
    )
    print("response   :", out)
