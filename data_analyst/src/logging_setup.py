"""Centralised logging for the CSV Data Analyst agent.

Project logging standard — three sinks, all under ``logs/``:

  logs/agentic.log
      The full pipeline narrative: every action run, validator verdict,
      transition decision, and important model-response text. The story of a run.

  logs/generic.log
      High-level operational events — startup, config, section boundaries,
      warnings, errors. The "is it running / where did it break" log. Also echoed
      to the console.

  logs/prompts_response/<action>.log
      Raw prompt + raw response, appended per call, one file per action — for
      prompt debugging.

Standard library only; no external dependencies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

# logs/ lives at the project root (data_analyst/), one level above this src/ package,
# so logs land in the same place regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
PROMPTS_DIR = LOG_DIR / "prompts_response"

_FILE_FMT = "%(asctime)s | %(name)-7s | %(levelname)-7s | %(message)s"
_CONSOLE_FMT = "%(levelname)-7s | %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Create the ``logs/`` tree and configure the agentic + generic loggers.

    Idempotent: safe to call multiple times (e.g. once at every session start).
    """
    global _configured
    if _configured:
        return

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    # agentic — file only (high volume; the full narrative)
    _file_logger("agentic", LOG_DIR / "agentic.log", level)

    # generic — file + console (low volume; what you watch while debugging)
    g = _file_logger("generic", LOG_DIR / "generic.log", level)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in g.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(_CONSOLE_FMT))
        g.addHandler(ch)

    _configured = True


def _file_logger(name: str, path: Path, level: int) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FILE_FMT))
        logger.addHandler(fh)
    return logger


def agentic() -> logging.Logger:
    """The pipeline-narrative logger (``logs/agentic.log``)."""
    return logging.getLogger("agentic")


def generic() -> logging.Logger:
    """The operational/debug logger (``logs/generic.log`` + console)."""
    return logging.getLogger("generic")


def log_section(title: str) -> None:
    """Mark a section boundary in both logs — we strategise/implement per section."""
    banner = f"{'=' * 12} {title} {'=' * 12}"
    generic().info(banner)
    agentic().info(banner)


def log_prompt_response(action: str, prompt: str, response: str) -> None:
    """Append one prompt/response pair to ``logs/prompts_response/<action>.log``."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    path = PROMPTS_DIR / f"{_safe(action)}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {ts} =====\n")
        f.write("----- PROMPT -----\n")
        f.write(prompt.rstrip() + "\n")
        f.write("----- RESPONSE -----\n")
        f.write(response.rstrip() + "\n")


def _safe(name: str) -> str:
    """Make an action name safe to use as a filename."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in name).lower()
