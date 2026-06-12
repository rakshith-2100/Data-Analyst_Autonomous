"""Sandbox — run a model-written code cell in an isolated subprocess.

Threat model is a *buggy* LLM, not a malicious one, so the isolation we need is:
  * a separate process  → a crash/segfault can't take down the orchestrator
  * a wall-clock timeout → an infinite loop can't hang forever (kill on expiry)
  * captured output      → stdout, traceback, and chart files land in known places

The cell runs with `df` preloaded (we read the CSV; the model never touches the
filesystem) and cwd set to a fresh temp workdir, so charts saved to ./out/ are captured
as artifacts. Matplotlib uses the headless Agg backend. Stateless: one fresh workdir per
exec — perfect for report tasks; a persistent namespace for chat comes later (Phase 8).

Harden-later: swap the subprocess for a Docker/e2b executor without touching callers.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.core import ExecResult
from src.logging_setup import agentic, generic, setup_logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "telco_churn.csv"

# Runner harness wrapped around the model's cell. Plain string (NOT an f-string) so the
# dict literal braces are safe; the two paths are substituted by replace().
_RUNNER = '''\
import os, sys
import matplotlib
matplotlib.use("Agg")
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv("__DATA__")
_src = open("__CELL__", encoding="utf-8").read()
exec(compile(_src, "__CELL__", "exec"), {"df": df, "pd": pd, "np": np, "plt": plt, "__name__": "__main__"})
'''


class Sandbox:
    """Runs one code cell per exec() call and returns an ExecResult."""

    def __init__(self, data_path: str | Path = DEFAULT_CSV, timeout: float = 15,
                 python: str | None = None):
        self.data_path = Path(data_path).resolve()
        self.timeout = timeout
        self.python = python or sys.executable

    def exec(self, code: str) -> ExecResult:
        workdir = Path(tempfile.mkdtemp(prefix="sbx_"))
        out_dir = workdir / "out"
        out_dir.mkdir()
        cell = workdir / "cell.py"
        cell.write_text(code, encoding="utf-8")
        runner = workdir / "runner.py"
        runner.write_text(self._runner_src(cell), encoding="utf-8")

        env = {**os.environ, "MPLBACKEND": "Agg"}
        try:
            proc = subprocess.run(
                [self.python, str(runner)],
                cwd=str(workdir), env=env,
                capture_output=True, text=True, timeout=self.timeout,
            )
            stdout = proc.stdout or ""
            error = None
            if proc.returncode != 0:
                error = (proc.stderr or "").strip() or f"exited with code {proc.returncode}"
        except subprocess.TimeoutExpired as e:
            stdout = _as_text(e.stdout)
            error = f"TimeoutError: code exceeded {self.timeout}s wall-clock limit"

        artifacts = sorted(str(p) for p in out_dir.glob("**/*") if p.is_file())
        result = ExecResult(stdout=stdout.strip(), error=error, artifacts=artifacts)
        self._log(code, result)

        # keep the workdir only when it produced artifacts worth serving
        if not artifacts:
            shutil.rmtree(workdir, ignore_errors=True)
        return result

    def _runner_src(self, cell: Path) -> str:
        return (_RUNNER
                .replace("__DATA__", self.data_path.as_posix())
                .replace("__CELL__", cell.as_posix()))

    def _log(self, code: str, result: ExecResult) -> None:
        status = "ok" if result.error is None else "error"
        generic().info("sandbox exec: %s (%d artifact(s))", status, len(result.artifacts))
        agentic().info(
            "EXECUTE [%s]\n--- code ---\n%s\n--- stdout ---\n%s\n--- error ---\n%s\n--- artifacts ---\n%s",
            status, code.strip(), result.stdout or "(none)", result.error or "(none)",
            ", ".join(result.artifacts) or "(none)",
        )


def _as_text(v) -> str:
    if v is None:
        return ""
    return v.decode(errors="replace") if isinstance(v, bytes) else v


if __name__ == "__main__":
    from src.validators.runtime import classify

    setup_logging()
    sb = Sandbox(DEFAULT_CSV, timeout=20)
    sb_fast = Sandbox(DEFAULT_CSV, timeout=4)  # for the runaway-loop case

    cases = [
        ("good + chart", sb,
         "print('churn rate:', round((df['Churn'] == 'Yes').mean(), 4))\n"
         "df['Churn'].value_counts().plot(kind='bar')\n"
         "plt.savefig('out/churn.png'); print('out/churn.png')"),
        ("missing column (KeyError)", sb, "print(df['Foo'].mean())"),
        ("dirty data (ValueError)", sb, "print(df['TotalCharges'].astype(float).mean())"),
        ("runaway loop (timeout)", sb_fast, "while True:\n    pass"),
    ]
    for name, box, code in cases:
        r = box.exec(code)
        v = classify(r)
        print(f"\n=== {name} ===")
        print(f"ok={v.ok}  error_kind={v.error_kind}  signature={v.signature}")
        print("stdout   :", (r.stdout or "")[:120])
        print("error    :", (r.error or "(none)").splitlines()[-1][:160])
        print("artifacts:", r.artifacts or "(none)")
