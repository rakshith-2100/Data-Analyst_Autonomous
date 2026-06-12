"""Runtime validator — judge an ExecResult and classify *how* it failed.

Free (no model). Turns a raw subprocess result into a Verdict the EXECUTE transition
can route on:

  * ok=True                         -> clean run, go to CHECK
  * error_kind = RESOURCE           -> timeout / memory, go to REDUCE
  * error_kind = MISSING_COLUMN | BAD_VALUE | NAME_OR_LOGIC | OTHER -> go to ENRICH->REPAIR

`signature` = a stable hash of (exception type + the cell line that raised), so a
*repeated* signature lets the transition detect "same error twice" and escalate instead
of retrying the identical message.

Classification is a small CLOSED set of buckets, deliberately NOT a per-error taxonomy.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.core import ExecResult, Verdict

# exception type name -> error_kind bucket (default OTHER)
_KIND = {
    "KeyError": "MISSING_COLUMN",       # df['missing'] in pandas
    "ValueError": "BAD_VALUE",          # e.g. could not convert string to float (TotalCharges)
    "TypeError": "BAD_VALUE",
    "TimeoutError": "RESOURCE",
    "MemoryError": "RESOURCE",
    "NameError": "NAME_OR_LOGIC",
    "AttributeError": "NAME_OR_LOGIC",
    "IndexError": "NAME_OR_LOGIC",
    "ZeroDivisionError": "NAME_OR_LOGIC",
    "ModuleNotFoundError": "NAME_OR_LOGIC",
    "ImportError": "NAME_OR_LOGIC",
}

_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)')


def classify(result: ExecResult) -> Verdict:
    """ExecResult -> Verdict at the `runtime` level."""
    if result.error is None:
        return Verdict(ok=True, level="runtime")
    exc = _exc_type(result.error)
    return Verdict(
        ok=False,
        level="runtime",
        reason=_last_line(result.error),
        error_kind=_KIND.get(exc, "OTHER"),
        signature=_signature(exc, result.error),
    )


def _last_line(error: str) -> str:
    lines = [ln for ln in error.strip().splitlines() if ln.strip()]
    return lines[-1].strip() if lines else ""


def _exc_type(error: str) -> str:
    """The exception class name from a traceback's final line ('KeyError: ...' -> 'KeyError')."""
    head = _last_line(error).split(":", 1)[0].strip()
    return head.split(".")[-1]  # pandas.errors.X -> X


def _signature(exc: str, error: str) -> str:
    """Stable hash of (exception, the cell line that raised) — prefers the model's cell frame."""
    frames = _FRAME_RE.findall(error)
    cell = [f for f in frames if Path(f[0]).name == "cell.py"]
    chosen = (cell or frames)[-1] if (cell or frames) else ("?", "?")
    loc = f"{Path(chosen[0]).name}:{chosen[1]}"
    return hashlib.md5(f"{exc}@{loc}".encode()).hexdigest()[:10]
