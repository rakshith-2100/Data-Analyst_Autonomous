"""ENRICH [sys] — build targeted error context for the failed cell. No model.

Reads the failed code + ExecResult, derives the error_kind, and assembles a focused
context block for REPAIR:
  * MISSING_COLUMN -> the real column list (use these exact names)
  * BAD_VALUE      -> the offending column's dtype / samples / issue + a cleaning hint
  * else           -> just the traceback tail

This is the "diagnose" half that used to be hidden inside REPAIR; pulling it out (free,
[sys]) means REPAIR only has to fix, never re-diagnose.
"""
from __future__ import annotations

from src.core import Verdict
from src.validators.runtime import classify

NAME = "ENRICH"


def run(state, ctx):
    result = ctx.data.get("exec_result")
    code = ctx.data.get("code", "")
    profile = ctx.profile
    verdict = classify(result) if result else None
    kind = verdict.error_kind if verdict else "OTHER"

    lines = ["The previous code failed.",
             f"ERROR: {verdict.reason if verdict else 'unknown'}",
             f"ERROR_KIND: {kind}"]

    if kind == "MISSING_COLUMN" and profile:
        lines.append("VALID COLUMNS (use these EXACT names): " + ", ".join(profile.column_names))
    elif kind == "BAD_VALUE" and profile:
        used = [c for c in profile.columns if c.name in code]
        for c in used:
            detail = f"  - {c.name}: dtype={c.dtype}, samples={c.samples}"
            if c.issue:
                detail += f", issue={c.issue}"
            lines.append(detail)
        lines.append("Hint: clean/convert the offending column before the operation, "
                     "e.g. pd.to_numeric(df['col'], errors='coerce').")
    else:
        lines.append("(no structured hint; rely on the traceback below)")

    if result and result.error:
        tail = "\n".join(result.error.strip().splitlines()[-4:])
        lines.append("TRACEBACK (tail):\n" + tail)
    lines.append("FAILED CODE:\n" + code)

    context = "\n".join(lines)
    ctx.data["enriched"] = context
    return context


def validate(output, ctx):
    return Verdict(ok=True, level="enrich", reason="context built")
