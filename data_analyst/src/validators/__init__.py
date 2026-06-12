"""Validators — the validation ladder.

Each level is the cheapest check that can catch its action's failure mode:
schema -> planning -> syntax -> runtime -> sanity -> grounding. Every validator
returns a Verdict; transitions route on it. Validators never route, transitions
never validate.
"""
