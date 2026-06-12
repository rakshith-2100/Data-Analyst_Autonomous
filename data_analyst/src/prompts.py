"""Load action / validator system prompts from prompts/*.md.

Project convention:
  * the model SYSTEM prompt lives in prompts/<area>/<name>.md  (area: actions | validators)
  * the USER message is built in the action's Python code (build_messages), from runtime
    data (profile + the one input) — so it is NOT stored here
  * prompts are edited as .md and grown stage by stage, never inlined in .py
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """load_prompt('actions/classify') -> contents of prompts/actions/classify.md."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
