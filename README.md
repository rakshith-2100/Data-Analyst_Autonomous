# CSV Data Analyst Agent

An agentic app that ingests a CSV and lets a user either **chat** with the data
(ask anything, get answers + charts) or **generate a report** (pick the charts and
stats they want, get a written analysis). Refinements loop back through chat.

The whole system is built from **three primitives** — one model, one tool
(`run_python`), one result shape — arranged as a **validated state machine**. There
is no second model and no per-error special-casing; "covering all cases" is done by
a small set of reusable *actions* plus a deterministic *transition* table.

---

## 1. Mental model

- **The model never does "the report" or "the chat."** It only ever does one tiny,
  bounded task at a time (classify a message, plan one step, write one code cell,
  write two sentences). Difficulty scales with *per-step* complexity, never with how
  big the overall job is.
- **An agent is a loop around a code-execution tool.** Model writes code → sandbox
  runs it → result (or error) feeds back → repeat until done.
- **The loop is really a state machine.** Each step is `state → action → validate →
  transition`. Making it explicit is what makes the system debuggable and testable.
- **Compute deterministically, narrate with the model.** Numbers and charts come
  from `pandas`/`matplotlib` code. The model only writes the *prose* on top of
  already-computed results. This kills hallucinated numbers.

### The two vocabularies (keep these separate)

| Term | What it is | Who owns it |
|---|---|---|
| **State** | where we are (e.g. `PLAN_STEP`, `EXECUTE`) | the machine |
| **Action** | a prompt-driven agent *or* a plain code step that does the work | `actions/` |
| **Validation** | a per-action check; its **type and strictness differ per action** | `validators/` |
| **Transition** | a deterministic `if/else` that routes to the next state based on the validation verdict — **not** itself a check | `transitions/` |

> Action does the work. Validation judges the work. Transition decides where to go.
> They are three different things in three different files.

---

## 2. Project structure

```
csv-analyst/
  README.md
  data/
    telco_churn.csv            # the working dataset (see §8)
  src/
    schemas.py                 # Profile, ColumnProfile, Task, ExecResult, Verdict, State
    profiler.py                # profile_csv(path) -> Profile   [pure, no model]
    sandbox.py                 # Sandbox.exec(code) -> ExecResult
    models.py                  # model clients + tiers (cheap / strong)
    orchestrator.py            # generic state-machine driver (reads the transition table)
    actions/                   # ALL agents/prompts live here, one file per action
      __init__.py              # ACTIONS registry: name -> module
      classify.py
      plan_step.py
      write_code.py
      execute.py               # [sys] plain code, no prompt
      enrich.py                # [sys] build targeted error context, no prompt
      repair.py
      reduce.py
      check.py
      compose.py
      ask.py
      plan_report.py
      refine_report.py
      dispatch.py              # [sys] fan-out, no prompt
      narrate.py
      assemble.py              # [sys] plain code, no prompt
    transitions/               # ALL routing (if/else) lives here, as data + functions
      __init__.py
      chat.py                  # transition table for the chat path
      report.py                # transition table for the report path
    validators/                # the validation LEVELS (see §5)
      schema.py                # enum / JSON-shape checks  (cheapest)
      planning.py              # do referenced columns exist in the profile?
      syntax.py                # compile() the code
      runtime.py               # ran without exception, under timeout?
      sanity.py                # does the result plausibly answer the question? (model)
      grounding.py             # every stated number traceable to a result? (model)
  eval/
    cases.yaml                 # question -> expected answer (seed your test set here)
    run_eval.py                # runs cases, reports pass rate, diffs against expected
  traces/                      # trace.jsonl per session (every action + verdict)
  app/                         # frontend (React) — built last
```

### How the orchestrator uses these three directories

The orchestrator is **generic** — it knows nothing about churn or charts. It does:

```python
state = State(name="CLASSIFY", data=...)
while not terminal(state):
    action   = ACTIONS[state.name]              # from actions/
    output   = action.run(state, ctx)           # the prompt (or [sys] code) executes
    verdict  = action.validate(output, ctx)     # from validators/, level chosen by the action
    state    = TRANSITIONS[ctx.path][state.name](verdict, state, output)  # from transitions/
    trace(state, action, verdict)               # append to traces/<session>.jsonl
```

Adding a new capability = add one file to `actions/`, register it, and add one row to
the relevant transition table. Nothing else changes.

---

## 3. The state machine (router tables)

`[agent]` = a prompt. `[sys]` = plain code, zero tokens. Counters are **named per state**
(`plan`/`code`/`repair`/`reduce`/`check`/`compose`); `N` = the repair cap.

### Chat path

| State | Action | Validation level | Transition (verdict → next) |
|---|---|---|---|
| `CLASSIFY` | `[agent]` label the message | schema (enum) | question→`PLAN_STEP` · unclear→`ASK` · refine→`PLAN_REPORT` · oos→`RESPOND` |
| `PLAN_STEP` | `[agent]` pick columns + op, 1-line plan, **no code** | planning | ok→`WRITE_CODE` · bad col & tries<2→`PLAN_STEP` · ambiguous→`ASK` |
| `WRITE_CODE` | `[agent]` one code cell from the plan | syntax | compiles→`EXECUTE` · else & tries<2→`WRITE_CODE` |
| `EXECUTE` | `[sys]` run in sandbox | runtime (**classifies** `error_kind`+`signature`) | clean→`CHECK` · `signature==last`→`ESCALATE` · `RESOURCE` & reduce<2→`REDUCE` · other error & repair<N→`ENRICH` · repair≥N→`ESCALATE` |
| `ENRICH` | `[sys]` build targeted context for the `error_kind` | — | →`REPAIR` |
| `REPAIR` | `[agent]` fix using the enriched context **only** | syntax | compiles→`EXECUTE` (repair++) · won't compile & code<2→`REPAIR` · else→`ESCALATE` |
| `REDUCE` | `[agent]` rewrite to sample/chunk | planning | ok & reduce<2→`EXECUTE` · else→`ESCALATE` |
| `CHECK` | `[agent]` does result answer the question? | sanity | yes→`COMPOSE` · no & check<2→`PLAN_STEP` · else→`ESCALATE` |
| `COMPOSE` | `[agent]` write the answer | grounding | grounded→`DELIVER` · else & compose<2→`COMPOSE` |
| `ASK` | `[agent]` one clarifying question | schema | →wait→`CLASSIFY` |
| `RESPOND` | `[agent]` short out-of-scope reply | — | →`DONE` |
| `ESCALATE` | `[sys]` pick the next recovery rung | — | `esc=0`→`PLAN_STEP` (restrategize, esc→1) · `esc=1` & budget→`WRITE_CODE` (strong model, esc→2) · else→`FAIL` |
| `DELIVER` | `[sys]` stream answer + charts | — | →`DONE`; next msg→`CLASSIFY` |
| `FAIL` | `[sys]` honest "couldn't compute X" | — | →`DONE` |

### Report path (reuses the chat actions — does not reinvent them)

| State | Action | Validation level | Transition (verdict → next) |
|---|---|---|---|
| `PLAN_REPORT` | `[agent]` checklist → **new** N tasks | planning | ok→`DISPATCH(all)` · else & tries<2→`PLAN_REPORT` |
| `REFINE_REPORT` | `[agent]` NL edit + existing tasks → diff `{add,drop,keep}` | planning | ok→`DISPATCH(changed only)` · else & tries<2→`REFINE_REPORT` |
| `DISPATCH` | `[sys]` fan out; each task runs `WRITE_CODE→EXECUTE→ENRICH→REPAIR→CHECK` in isolation; reuse cached results for `keep` | all tasks terminal (`DONE_TASK`/`FAILED_TASK`) | all settled→`NARRATE` |
| `NARRATE` | `[agent]` prose from `{done, failed}` results | grounding | grounded→`ASSEMBLE` · else & tries<2→`NARRATE` |
| `ASSEMBLE` | `[sys]` stitch prose + chart files | artifacts present | →`DELIVER` |

**`PLAN_REPORT` mirrors `PLAN_STEP`** — same planning validation against the profile,
same retry-on-bad-column. The only difference is it emits *N* task specs instead of
one. After that, `DISPATCH` runs the **exact same** `WRITE_CODE → EXECUTE → ENRICH →
REPAIR → CHECK` actions per task, just in parallel and stateless. One engine, two entry points.

**Refine is not rebuild.** A refine message ("drop the pie, add a forecast") routes to
`REFINE_REPORT` (not `PLAN_REPORT`): it emits a `{add, drop, keep}` *diff* against the
existing task list, and `DISPATCH` runs only the `add`ed tasks while **reusing cached
results** for `keep`. Each task has two terminals — `DONE_TASK` or `FAILED_TASK` — so one
failed task doesn't sink the report; `NARRATE` reports the gap honestly instead of
inventing the number.

---

## 4. How prompts are structured

This is the core of the build. Every `[agent]` action follows the **same anatomy**, and
the differences between actions are deliberate and small.

### 4.1 Anatomy of every action prompt

```
SYSTEM:
  ROLE        – one sentence: what this agent is and the ONE thing it does
  INPUTS      – names the inputs it will receive
  RULES       – hard constraints (use only profile columns; no prose; etc.)
  OUTPUT      – an exact, parseable contract (a JSON shape OR a single code block)

USER (content assembled by build_messages):
  PROFILE     – the compact data profile (or just the slice this action needs)
  INPUT       – the one thing this action operates on (the message / plan / traceback)
```

### 4.2 Five non-negotiable principles

1. **Single responsibility.** One action does exactly one thing. If a prompt says "do
   X and then Y," split it into two actions. This is what keeps each call cheap — the
   model is never juggling multiple concerns.
2. **Minimal context.** An action sees the **profile + its one input**, never the full
   chat history. Independent tasks must not share a conversation. (Chat keeps a short
   rolling summary; report tasks are fully stateless.)
3. **Structured output, always.** Either strict JSON (with the shape in the system
   prompt) or a single fenced ```python block. Never free prose that you then have to
   regex. Validate the shape before doing anything with it.
4. **Profile is the source of truth for columns.** Every prompt that names data is told
   the exact column list. The model misremembers casing constantly; handing it the
   real names removes a whole class of errors.
5. **Don't feed the solution, feed the context.** For `REPAIR`, give the enriched
   traceback (real column list, offending values) — not a step-by-step fix. The model
   reasons; you supply what it can't see. Hand-written fix-recipes don't scale.

### 4.3 Each action module exports the same interface

```python
# actions/plan_step.py
NAME = "PLAN_STEP"
MODEL_TIER = "cheap"          # which model tier this action uses

SYSTEM = """You are a data-analysis planner. Given a dataset profile and a user
question, output a ONE-step plan: which columns to use and what single operation to
perform. Do NOT write code. Use ONLY column names that appear in the profile.
Respond with ONLY this JSON object and nothing else:
{"columns": [...], "operation": "...", "plan": "<one sentence>"}"""

def build_messages(ctx):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content":
            f"PROFILE:\n{ctx.profile.as_prompt()}\n\nQUESTION:\n{ctx.question}"},
    ]

def parse(raw: str) -> dict:
    return json.loads(strip_fences(raw))

def validate(parsed: dict, ctx) -> Verdict:        # PLANNING level
    bad = [c for c in parsed["columns"] if c not in ctx.profile.column_names]
    if bad:
        return Verdict(ok=False, level="planning",
                       reason=f"unknown columns {bad}")
    return Verdict(ok=True, level="planning")
```

The orchestrator only knows `build_messages`, `parse`, `validate`, `MODEL_TIER`.

### 4.4 Concrete prompt examples per action

Each block is the **system prompt** (the `build_messages` user content is always
`PROFILE + the input named in INPUTS`).

**CLASSIFY** — schema-validated router
```
ROLE:   You route a user message about a dataset.
INPUTS: profile, user message.
RULES:  Choose exactly one label.
OUTPUT: {"label": "question|unclear|refine|out_of_scope", "reason": "<short>"}
        Output only the JSON object.
```

**PLAN_STEP** — see 4.3 above (planning-validated).

**WRITE_CODE** — syntax-validated code generator
```
ROLE:   You write ONE pandas/matplotlib code cell to execute a given plan.
INPUTS: profile, plan (columns + operation).
RULES:  The DataFrame `df` is already loaded. Use ONLY columns from the profile.
        Save any chart to ./out/ and print its path. print() any value to report.
        Do not read files. Do not import anything outside: pandas, numpy, matplotlib.
OUTPUT: a single ```python code block, nothing before or after.
```

**REPAIR** — syntax-validated fixer (gets *enriched* error)
```
ROLE:   You fix a code cell that failed.
INPUTS: the failed code, and an enriched error (traceback + real column list +
        offending values where relevant).
RULES:  Change as little as possible. Use ONLY columns from the profile.
OUTPUT: a single corrected ```python code block, nothing else.
```

**REDUCE** — for timeout / memory (a *different* fix, not a bug fix)
```
ROLE:   The previous code was correct but too expensive (timed out / ran out of memory).
INPUTS: the code, the resource error.
RULES:  Rewrite to sample or chunk the data (e.g. .sample(n), chunked aggregation)
        while answering the same question. Use ONLY profile columns.
OUTPUT: a single ```python code block.
```

**CHECK** — sanity validator (the agent IS the validator here)
```
ROLE:   You judge whether a computed result actually answers the question.
INPUTS: question, the code that ran, its stdout/result.
RULES:  Check it used the right columns, has a plausible shape, and addresses the ask.
OUTPUT: {"answers": true|false, "reason": "<short>"}
```

**COMPOSE** — grounding-validated answer writer
```
ROLE:   You write a concise answer to the user's question.
INPUTS: question, the computed result, chart path (if any).
RULES:  Use ONLY numbers that appear in the result — never invent or round-trip from
        memory. Reference the chart if present. 2–4 sentences.
OUTPUT: plain prose.
```

**PLAN_REPORT** — planning-validated, emits N tasks (mirrors PLAN_STEP)
```
ROLE:   You expand a checklist of requested outputs into a task list.
INPUTS: profile, checklist (e.g. ["pie of churn by tier", "bar of revenue by region"]).
RULES:  One task per checklist item. Each task = {id, kind: "chart"|"stat",
        columns: [...], operation, instruction}. Use ONLY profile columns.
OUTPUT: a JSON array of task objects, nothing else.
```

**NARRATE** — grounding-validated report writer
```
ROLE:   You write the report's prose from a set of completed task results.
INPUTS: profile, list of {task, result, chart_path}.
RULES:  One short section per task, using its result. Every number must be traceable
        to a result. Call out what is surprising. Do not invent findings.
OUTPUT: markdown: a 2–3 sentence executive summary, then one section per task.
```

**REFINE_REPORT** — planning-validated, edits an existing report (mirrors PLAN_REPORT)
```
ROLE:   You translate a refine instruction into edits on an existing task list.
INPUTS: profile, the current task list, the instruction ("drop the pie, add a forecast").
RULES:  Output a diff, not a new report. Reuse existing task ids in drop/keep; only
        genuinely new outputs go in add. Use ONLY profile columns.
OUTPUT: {"add": [<task>...], "drop": [<task id>...], "keep": [<task id>...]}, nothing else.
```

`execute`, `enrich`, `dispatch`, `assemble` have **no prompt** — they are plain code.

---

## 5. Validation levels (the ladder)

Your key point: validation differs per action. Each action picks the **cheapest check
that can actually catch its failure mode**. They climb from mechanical to semantic:

| Level | File | Cost | Catches | Used by |
|---|---|---|---|---|
| schema | `validators/schema.py` | free | output isn't the expected JSON shape / enum | `CLASSIFY`, `ASK` |
| planning | `validators/planning.py` | free | references a column not in the profile | `PLAN_STEP`, `PLAN_REPORT`, `REDUCE` |
| syntax | `validators/syntax.py` | free (`compile()`) | code won't parse / banned import | `WRITE_CODE`, `REPAIR` |
| runtime | `validators/runtime.py` | free | raised an exception / hit timeout; **classifies `error_kind` + `signature`** | `EXECUTE` |
| sanity | `validators/sanity.py` | 1 model call | ran clean but answers the wrong question | `CHECK` |
| grounding | `validators/grounding.py` | code or 1 model call | a stated number isn't in the results | `COMPOSE`, `NARRATE` |

Four of six levels cost **zero model calls**. You only spend a call on the two genuinely
judgment-laden checks. Never run an expensive validation where a cheap one suffices.

---

## 6. Core data structures (`src/schemas.py`)

```python
@dataclass
class ColumnProfile:
    name: str
    dtype: str               # what pandas inferred
    n_null: int
    n_unique: int
    samples: list            # 3–5 example values
    stats: dict | None       # min/max/mean for numerics
    issue: str | None        # e.g. "numeric-looking but contains blank strings"

@dataclass
class Profile:
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    @property
    def column_names(self): return [c.name for c in self.columns]
    def as_prompt(self) -> str: ...   # compact text the model sees

@dataclass
class Task:
    id: str
    kind: str                # "chart" | "stat"
    columns: list[str]
    operation: str
    instruction: str
    artifact_path: str | None = None

@dataclass
class ExecResult:
    stdout: str
    error: str | None        # enriched traceback or None
    artifacts: list[str]     # files written to ./out/ this call

@dataclass
class Verdict:
    ok: bool
    level: str               # which validation level produced this
    reason: str = ""
    error_kind: str | None = None   # runtime only: MISSING_COLUMN|BAD_VALUE|NAME_OR_LOGIC|RESOURCE|OTHER
    signature: str | None = None    # hash(error_type + "file:line") — detects "same error twice"

@dataclass
class State:
    name: str
    data: dict
    counters: dict = field(default_factory=dict)  # named: plan/code/repair/reduce/check/compose
    esc_level: int = 0       # escalation rung: 0 none · 1 restrategized · 2 strong model
    tier: str = "cheap"      # cheap | strong  (ESCALATE may flip to strong)
```

---

## 7. Models — OpenAI GPT

We use **OpenAI GPT models** throughout. The axis that matters is **tool-call /
structured-output reliability**, not raw chat IQ — every action returns strict JSON or a
single code block, so reliable structured output is exactly what we're buying. Prices
move — re-check before committing.

| Tier | Model | Use for |
|---|---|---|
| **cheap (default)** | `gpt-4.1-mini` (drop to `gpt-4.1-nano` for the trivial classify/plan calls) | everything by default — fast, cheap, reliable structured output |
| **strong (escalation only)** | `gpt-4.1` (or a larger GPT) | only when a cheap model is provably stuck (same error after enriched retry) |

Default everything to the **cheap GPT tier**. `ESCALATE` swaps to the strong GPT model only
when the cheap one is provably stuck. Don't build tiering until you feel the need — one
client and one default model to start.

---

## 8. Dataset

**Telco Customer Churn** — 7,043 rows × 21 columns, one row per customer, mix of
categoricals (contract, payment method, internet service), numerics (tenure, monthly
charges, total charges), and a binary `Churn` target.

```bash
wget -O data/telco_churn.csv \
  "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
```

**Why this one:** it has a built-in gotcha — `TotalCharges` looks numeric but contains
blank strings, so a naive `.mean()` raises. That makes it the perfect test of the
`EXECUTE → REPAIR` path and a great first eval case. Known answers to verify against:
month-to-month contracts churn far more than longer ones; higher monthly charges
correlate with churn.

---

## 9. Build order

Each stage runs end-to-end before the next.

1. **`profiler.py`** — `profile_csv(path) -> Profile`. Pure, no model. It is the input
   to every action and validator and the seed for eval case #1. **Start here.**
2. **`sandbox.py` + the loop** — wire `WRITE_CODE → EXECUTE → REPAIR → CHECK` for one
   question. Subprocess + timeout is fine to start; harden isolation (Docker/e2b) later.
3. **`transitions/chat.py` + orchestrator** — make the chat path traverse the table.
4. **Report path** — `PLAN_REPORT → DISPATCH → NARRATE → ASSEMBLE`, reusing stage 2.
5. **`eval/`** — seed `cases.yaml` (include the `TotalCharges` case); run on every change.
6. **`app/`** — the React frontend, connected last.

---

## 10. Gotchas worth pinning

- **Persistent vs. fresh namespace.** Chat keeps one sandbox across turns (so "now as a
  pie" works). Report tasks each get a fresh, stateless sandbox. This single decision
  is what keeps a cheap model coherent.
- **Pin the profile every turn; never replay full history.** Summarize instead — long
  histories are where small models start contradicting themselves.
- **Cap everything.** Per-state `tries`, a global iteration cap, and a wall-clock
  timeout on every `sandbox.exec`.
- **Write `traces/` from day one.** When the agent does something baffling, the trace is
  the only way you'll know why — and it powers the eval harness.
- **Same error twice = your feedback didn't land.** Escalate (enrich → change strategy →
  stronger model → bail), don't repeat the identical message.
