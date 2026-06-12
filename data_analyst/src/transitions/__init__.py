"""Transition registry: path -> {state name: transition fn}."""
from . import chat, report, task

TRANSITIONS = {"chat": chat.TABLE, "report": report.TABLE, "task": task.TABLE}
