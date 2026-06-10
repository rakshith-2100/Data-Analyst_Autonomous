# Project context — CSV Data Analyst Agent (conversation summary)

Paste this into a new chat to bring it fully up to speed. It captures every decision
made so far, the reasoning behind each, and what comes next. Nothing has been coded
yet — the next concrete step is writing `profile_csv`.

---

## What I'm building

An **upskilling project**: an agentic AI app where a user uploads a CSV and can either
**chat** with the data (ask anything, get answers + charts) or **generate a report**
(pick charts/stats from a checklist, get a written analysis). After a report is
generated, the user can refine it in chat ("drop the pie, add a forecast") and it
updates in place. I'm cost-sensitive and based in India; I want **non-Anthropic**
models because the Anthropic ones are too expensive for me.

I've already seen a clickable UX mockup of the flow (upload → processing → chat/report
fork → report builder → report with a refine bar) and agreed it's the right shape.

## Core decisions (settled)

- **Three primitives:** one model, one tool (`run_python`), one result shape
  (`ExecResult`). Everything is an arrangement of these — no second model, no
  per-error special-casing.
- **The model never does "the whole job."** It does one tiny bounded task per call
  (classify / plan one step / write one code cell / write a couple of sentences).
  This is the answer to "is a single LLM enough?" — yes, because difficulty scales
  with per-step complexity, not job size.
- **Compute-then-narrate:** numbers and charts come from deterministic
  pandas/matplotlib code; the model only writes prose over already-computed results.
  This is the main defense against hallucinated numbers.
- **Architecture = a validated state machine** with three *separate* concepts:
  - **Action** = the work (a prompt-driven agent, or plain `[sys]` code). Lives in `actions/`.
  - **Validation** = a per-action check whose *type/strictness differs per action*. Lives in `validators/`.
  - **Transition** = a deterministic `if/else` that routes to the next state from the verdict — NOT itself a check. Lives in `transitions/`.
  - A generic **orchestrator** reads the transition table and drives the loop.
- **Chat vs report are the same engine, two entry points.** Report = `PLAN_REPORT`
  emits N task specs, then the *same* `WRITE_CODE → EXECUTE → REPAIR → CHECK` actions
  run per task, in parallel and stateless. Chat is one persistent-state loop. The user
  explicitly asked that PLAN_REPORT mirror the chat planning step — it does.
- **Persistent vs fresh namespace:** chat keeps one sandbox across turns (so "now as a
  pie" works); each report task gets a fresh, stateless sandbox. This is the single
  most important low-level decision for keeping a cheap model coherent.

## How prompts are structured (I care a lot about this)

Every `[agent]` action has the same anatomy:
- **System prompt:** ROLE (one sentence, one job) + INPUTS + RULES (hard constraints,
  esp. "use only columns from the profile") + OUTPUT (an exact JSON shape OR a single
  fenced code block).
- **User content:** the compact data **profile** + the **one input** this action
  operates on. Never the full chat history.

Five rules: single responsibility (split "do X then Y" into two actions); minimal
context (profile + one input only); always structured/parseable output; the profile is
the source of truth for column names; for repairs, feed *context* (real columns,
offending values) not a step-by-step solution.

Each action module exports the same interface: `SYSTEM`, `MODEL_TIER`,
`build_messages(ctx)`, `parse(raw)`, `validate(parsed, ctx) -> Verdict`.

## Validation ladder (cheapest check that catches the failure)

schema (enum/JSON shape) → planning (do columns exist in profile?) → syntax
(`compile()`) → runtime (exception/timeout?) → sanity (right answer? — 1 model call) →
grounding (numbers traceable? — code or 1 model call). Four of six cost zero model
calls. Only `CHECK` (sanity) and `COMPOSE`/`NARRATE` (grounding) spend a call.

## Failure handling philosophy

- **Loud failures (they throw):** syntax, type, KeyError, the Telco `TotalCharges`
  blank-string ValueError — caught *free* by the loop; traceback feeds back, model
  fixes, retries (capped). No special code.
- **Silent failures (run clean but wrong):** wrong column, wrong question, dirty data,
  hallucinated number — need preventive guards: rich profile, visible code, the
  compute-then-narrate split, and the eval set.
- **Tailored feedback by error kind, via escalation, not a rulebook:** raw traceback →
  enriched (inject real column list for KeyError, offending values for ValueError,
  "sample/chunk" hint for timeout/memory) → change strategy or swap to a stronger model
  → bail honestly. Same error twice means the feedback didn't land. Keep it to a small
  `enrich_feedback()` function (~4 branches), not a taxonomy.
- **How we KNOW it's covered:** an **eval set** (`question -> expected`) seeded with the
  known-hard cases, run on every change, plus `trace.jsonl` to see where a failing run
  went wrong. Measure coverage; don't hope.

## Models (cost-first, non-Anthropic; prices early–mid 2026, re-check)

- **Default: Gemini 2.5 / 3.1 Flash** (~$0.25–0.30 in / $1.50 out) — 1M context, fast,
  reliable tool use. Sweet spot.
- DeepSeek V3.2 (~$0.14–0.28 / $0.28–0.42) — cheapest, but keep a fallback (availability).
- GPT-4.1 nano/mini (~$0.10 / $0.40 nano) — if tool-calling reliability bites.
- Qwen 3 Coder — open/self-host via Groq/Together.
- `ESCALATE` swaps to a stronger model only when a cheap one is provably stuck.

## Dataset

**Telco Customer Churn**, 7,043 × 21, direct download:
`https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv`
Key feature: `TotalCharges` looks numeric but has blank strings → naive `.mean()` raises.
This is the test case for the EXECUTE→REPAIR path and eval case #1. Known answers to
verify: month-to-month churns far more than longer contracts; higher monthly charges
correlate with churn.

## Directory layout (agreed)

```
src/{schemas, profiler, sandbox, models, orchestrator}.py
src/actions/      one file per action (classify, plan_step, write_code, execute[sys],
                  repair, reduce, check, compose, ask, plan_report, dispatch[sys],
                  narrate, assemble[sys])
src/transitions/  chat.py, report.py  (the if/else router tables)
src/validators/   schema, planning, syntax, runtime, sanity, grounding
eval/             cases.yaml, run_eval.py
traces/           trace.jsonl per session
app/              React frontend (built last)
```

## Build order

1. **`profiler.py` — `profile_csv(path) -> Profile`** (pure, no model). The input to
   every action/validator and seed for eval #1. **THIS IS THE NEXT STEP.**
2. sandbox + the `WRITE_CODE→EXECUTE→REPAIR→CHECK` loop for one question.
3. transitions/chat.py + orchestrator to traverse the chat path.
4. report path (PLAN_REPORT→DISPATCH→NARRATE→ASSEMBLE), reusing stage 2.
5. eval harness.
6. React frontend.

## Where we are / what to do next

Nothing is coded yet; the full architecture is designed (see the accompanying
`README.md` for the in-depth version, including all the prompt templates). The
immediate next action is to **write `profile_csv` against the Telco dataset** — load
the CSV, emit shape, per-column dtype/null-count/cardinality/samples, and flag messy
columns like `TotalCharges`. Then build eval case #1 around it.

When you continue: please keep responses concrete and code-first from here, default to
Gemini Flash in any examples, and respect the action/validation/transition separation
above (they are three different files, not one).
