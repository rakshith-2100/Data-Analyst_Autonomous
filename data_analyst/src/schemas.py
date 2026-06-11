"""Data schemas — describe the dataset itself.

Pure type contracts: dataclasses only, no logic, no model, no pandas. The profiler
returns a Profile built from ColumnProfiles — the source of truth for column names
that every prompt embeds via Profile.as_prompt().

The agent's operational types (State, Verdict, ExecResult, Task) live in core.py.
Both modules are leaves — they import nothing internal — which keeps actions /
validators / transitions decoupled and free of circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColumnProfile:
    """Everything we know about one column, computed deterministically."""
    name: str
    dtype: str                  # what pandas inferred (object, int64, float64, ...)
    n_null: int
    n_unique: int
    samples: list               # 3-5 example values
    stats: dict | None = None   # {"min","max","mean"} for numerics; None otherwise
    issue: str | None = None    # e.g. "numeric-looking but contains 11 blank strings"


@dataclass
class Profile:
    """A compact, trustworthy description of a CSV — the source of truth for columns."""
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def as_prompt(self) -> str:
        """Render the compact text the model sees in every action's user message."""
        lines = [f"DATASET: {self.n_rows} rows x {self.n_cols} columns", "", "COLUMNS:"]
        for c in self.columns:
            parts = [f"- {c.name} ({c.dtype})", f"{c.n_unique} unique", f"{c.n_null} null"]
            if c.stats:
                parts.append("min={min} max={max} mean={mean}".format(**c.stats))
            if c.samples:
                parts.append("e.g. " + ", ".join(str(s) for s in c.samples[:4]))
            line = " | ".join(parts)
            if c.issue:
                line += f"  [!] {c.issue}"
            lines.append(line)
        return "\n".join(lines)
