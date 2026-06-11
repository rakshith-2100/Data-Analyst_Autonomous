"""profile_csv(path) -> Profile — turn a raw CSV into a compact, trustworthy profile.

Pure and deterministic: pandas only, no model, no network. This is the input to
every action and validator (every prompt embeds Profile.as_prompt()) and the seed
for eval case #1 — the TotalCharges blank-string gotcha.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.logging_setup import agentic, generic, setup_logging
from src.schemas import ColumnProfile, Profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "telco_churn.csv"

_MAX_SAMPLES = 4


def profile_csv(path: str | Path) -> Profile:
    """Load a CSV and describe every column. No model involved."""
    path = Path(path)
    df = pd.read_csv(path)
    generic().info("profiling %s : %d rows x %d cols", path.name, df.shape[0], df.shape[1])

    columns = [_profile_column(df[name]) for name in df.columns]
    profile = Profile(n_rows=int(df.shape[0]), n_cols=int(df.shape[1]), columns=columns)

    flagged = [c.name for c in columns if c.issue]
    if flagged:
        generic().info("flagged messy columns: %s", ", ".join(flagged))
    agentic().info("PROFILE\n%s", profile.as_prompt())
    return profile


def _profile_column(series: pd.Series) -> ColumnProfile:
    dtype = str(series.dtype)
    n_null = int(series.isna().sum())
    n_unique = int(series.nunique(dropna=True))
    samples = [_py(v) for v in series.dropna().unique()[:_MAX_SAMPLES]]

    stats = None
    if pd.api.types.is_numeric_dtype(series):
        stats = {
            "min": _py(series.min()),
            "max": _py(series.max()),
            "mean": round(float(series.mean()), 2),
        }

    return ColumnProfile(
        name=str(series.name),
        dtype=dtype,
        n_null=n_null,
        n_unique=n_unique,
        samples=samples,
        stats=stats,
        issue=_detect_issue(series, dtype),
    )


def _detect_issue(series: pd.Series, dtype: str) -> str | None:
    """Flag a column that looks numeric but isn't cleanly typed (e.g. TotalCharges)."""
    if dtype != "object":
        return None
    nonnull = series.dropna()
    if nonnull.empty:
        return None
    coerced = pd.to_numeric(nonnull, errors="coerce")
    n_parseable = int(coerced.notna().sum())
    n_bad = int(len(nonnull) - n_parseable)
    # a mostly-numeric column with a few unparseable values is the real gotcha
    if n_parseable and n_bad and (n_parseable / len(nonnull)) > 0.5:
        n_blank = int(nonnull.astype(str).str.strip().eq("").sum())
        detail = f"{n_bad} non-numeric value(s)"
        if n_blank:
            detail += f" ({n_blank} blank string(s))"
        return f"numeric-looking but contains {detail}; naive .mean() will raise"
    return None


def _py(v):
    """Best-effort convert a numpy/pandas scalar to a plain Python value."""
    try:
        return v.item()
    except AttributeError:
        return v


if __name__ == "__main__":
    setup_logging()
    p = profile_csv(DEFAULT_CSV)
    print(p.as_prompt())
    print("\nflagged columns:", [c.name for c in p.columns if c.issue])
