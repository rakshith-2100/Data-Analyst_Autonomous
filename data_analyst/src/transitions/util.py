"""Helpers for building the next State in transitions — construction only, no logic.

A transition reads a Verdict and returns a State; these keep that one line readable while
preserving data / esc_level / tier and managing the named retry counters.
"""
from __future__ import annotations

from src.core import State


def goto(name, state, *, counters=None, data=None, esc_level=None, tier=None) -> State:
    return State(
        name=name,
        data=state.data if data is None else data,
        counters=state.counters if counters is None else counters,
        esc_level=state.esc_level if esc_level is None else esc_level,
        tier=state.tier if tier is None else tier,
    )


def bump(state, key) -> dict:
    c = dict(state.counters)
    c[key] = c.get(key, 0) + 1
    return c


def reset(state, *keys) -> dict:
    c = dict(state.counters)
    for k in keys:
        c.pop(k, None)
    return c


def count(state, key) -> int:
    return state.counters.get(key, 0)
