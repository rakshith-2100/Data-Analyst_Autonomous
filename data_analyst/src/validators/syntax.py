"""Syntax validator — free (compile + AST). Used by WRITE_CODE and REPAIR.

Two checks, both before the code ever runs:
  1. it parses (no SyntaxError)
  2. it imports ONLY allowed packages (the import allowlist) — a stray `import os` /
     `import requests` is rejected here, not at runtime.

A new detection (e.g. another banned import) goes HERE; the transitions don't change —
this is just another way `ok=False` at the syntax level, which WRITE_CODE already routes.
"""
from __future__ import annotations

import ast

from src.core import Verdict

ALLOWED_IMPORTS = {"pandas", "numpy", "matplotlib"}


def validate_code(code, level: str = "syntax", allowed=ALLOWED_IMPORTS) -> Verdict:
    """Verify the code parses and imports only allowed top-level packages."""
    if not isinstance(code, str) or not code.strip():
        return Verdict(ok=False, level=level, reason="empty code")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return Verdict(ok=False, level=level, reason=f"SyntaxError: {e.msg} (line {e.lineno})")
    bad = _banned_imports(tree, allowed)
    if bad:
        return Verdict(ok=False, level=level, reason=f"banned import(s): {sorted(bad)}")
    return Verdict(ok=True, level=level)


def _banned_imports(tree: ast.AST, allowed) -> set:
    bad = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in allowed:
                    bad.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top not in allowed:
                    bad.add(top)
    return bad
