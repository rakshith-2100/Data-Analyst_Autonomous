# Transition Tables — the state-machine routers

This is the routing layer of the architecture, pulled out on its own so it's easy to
review and edit. It is the **planner you write by hand**: every row is a deterministic
`if/else` that reads a validation *verdict* and decides the next state. The model is
never asked "what should I do next" — that answer lives here.

> **Action** does the work (`actions/`). **Validation** judges the work (`validators/`).
> **Transition** (this file) decides where to go next. Three different things.

Legend:
- `[agent]` = a prompt-driven model call · `[sys]` = plain code, **zero tokens**
- Counters are **named per state** (`plan`/`code`/`repair`/`reduce`/`check`/`compose`),
  not one blurred `tries`. `N` = the repair cap (small, e.g. 2–3).
- Validation level = the cheapest check that can catch *this* action's failure mode

---

## What the transitions read (the routing data)

A transition only ever *reads* a `Verdict` and the current `State` and returns the next
`State`. To route in depth, those two objects carry a little structure — but the
transition still computes nothing; it just branches on these fields.

```python
# set by the runtime validator (validators/runtime.py)
Verdict.error_kind ∈ {MISSING_COLUMN, BAD_VALUE, NAME_OR_LOGIC, RESOURCE, OTHER}
Verdict.signature  = hash(error_type + "file:line")   # to detect "same error twice"

# carried on State
State.counters  = {plan, code, repair, reduce, check, compose}   # named, capped
State.esc_level ∈ {0: none, 1: restrategized, 2: strong_model}
State.tier      ∈ {cheap, strong}                                # ESCALATE may flip it
```

`error_kind` is a **closed set of ~5 buckets, not a taxonomy** — it satisfies the
"don't build a rulebook" rule. The validator *classifies*, the `ENRICH` action builds
*targeted context* per bucket, and the transition *routes* on the bucket. Three files.

---

## Chat path  (`transitions/chat.py`)

One persistent-state loop. The sandbox namespace survives across turns, so a follow-up
like "now show it as a pie" can build on the previous result.

| State | Action | Validation | Transition (verdict → next state) |
|---|---|---|---|
| `CLASSIFY` | `[agent]` label the message | schema (enum) | `question`→`PLAN_STEP` · `unclear`→`ASK` · `refine`→`REFINE_REPORT` · `out_of_scope`→`RESPOND` |
| `PLAN_STEP` | `[agent]` pick columns + op, 1-line plan, **no code** | planning | ok→`WRITE_CODE` · bad column & `plan<2`→`PLAN_STEP` · ambiguous→`ASK` |
| `WRITE_CODE` | `[agent]` one pandas/matplotlib cell from the plan | syntax | compiles→`EXECUTE` · else & `code<2`→`WRITE_CODE` |
| `EXECUTE` | `[sys]` run cell in the sandbox | runtime (**classifies** `error_kind` + `signature`) | clean→`CHECK` *(reset repair/reduce)* · **`signature==last`→`ESCALATE`** *(feedback didn't land)* · `error_kind=RESOURCE` & `reduce<2`→`REDUCE` · other error & `repair<N`→`ENRICH` · `repair≥N`→`ESCALATE` |
| `ENRICH` | `[sys]` build targeted context for the `error_kind` — `MISSING_COLUMN`→real column list · `BAD_VALUE`→offending values + dtype · `NAME_OR_LOGIC`/`OTHER`→raw traceback | — *(pure code, no check)* | always→`REPAIR` |
| `REPAIR` | `[agent]` fix using the **enriched context only** (diagnosis already done) | syntax | compiles→`EXECUTE` *(repair++)* · won't compile & `code<2`→`REPAIR` · else→`ESCALATE` |
| `REDUCE` | `[agent]` rewrite to sample/chunk the data | planning | ok & `reduce<2`→`EXECUTE` *(reduce++)* · else→`ESCALATE` |
| `CHECK` | `[agent]` does the result answer the question? | sanity | yes→`COMPOSE` · no & `check<2`→`PLAN_STEP` · else→`ESCALATE` |
| `COMPOSE` | `[agent]` write the answer over the result | grounding | grounded→`DELIVER` · else & `compose<2`→`COMPOSE` |
| `ASK` | `[agent]` one clarifying question | schema | → wait for reply → `CLASSIFY` |
| `RESPOND` | `[agent]` short out-of-scope reply | — | → `DONE` |
| `ESCALATE` | `[sys]` pick the next recovery rung | — | `esc=0`→`PLAN_STEP` *(restrategize; esc→1)* · `esc=1` & budget→`WRITE_CODE` *(strong model; tier=strong, esc→2)* · else→`FAIL` |
| `DELIVER` | `[sys]` stream answer + charts to the user | — | → `DONE`; next message → `CLASSIFY` |
| `FAIL` | `[sys]` honest "couldn't compute X" message | — | → `DONE` |

**Terminal states:** `DONE`, `FAIL`.

### The `EXECUTE → REPAIR` split (why it is four states, not one)

The old single hop `exception→REPAIR` quietly did two jobs: *diagnose the failure* and
*fix the code*. They are now separate so the diagnosis is **free**:

1. `EXECUTE` runs; the **runtime validator** classifies the failure into one `error_kind`
   + a `signature`.
2. The **transition** routes: resource problems take the `REDUCE` path; a *repeated*
   `signature` short-circuits straight to `ESCALATE` (retrying the identical message is
   banned); everything else goes to `ENRICH`.
3. `ENRICH` (`[sys]`, zero tokens) assembles the *targeted* context for that bucket.
4. `REPAIR` (`[agent]`) only fixes — it never has to guess what went wrong.

Cost is unchanged (one paid call, as before) but the pipeline is more deterministic and
the "same error twice" invariant is now a real edge instead of a hope.

### The escalation ladder (`ESCALATE` in depth)

`ESCALATE` is not "swap model or bail" — it is a **cheapest-first ladder**, one rung per
visit, each capped by `esc_level`:

| `esc_level` | Rung | Routes to |
|---|---|---|
| 0 | **Change strategy** — the plan itself may be wrong; replan with different columns/op | `PLAN_STEP` (esc→1, reset repair/code) |
| 1 | **Stronger model** — the plan is fine, the cheap model can't execute it | `WRITE_CODE` (tier=strong, esc→2, reset repair) |
| 2 | **Bail honestly** — out of rungs (or out of budget) | `FAIL` |

(Enrichment is already the first, cheapest rung — it happens in `ENRICH` before we ever
reach `ESCALATE`.)

---

## Report path  (`transitions/report.py`)

Same engine, second entry point. `PLAN_REPORT` mirrors `PLAN_STEP` (same planning
validation, same retry-on-bad-column) but emits **N** task specs instead of one. Each
task then runs the **exact same** inner loop — in parallel and **stateless** (fresh
sandbox per task).

| State | Action | Validation | Transition (verdict → next state) |
|---|---|---|---|
| `PLAN_REPORT` | `[agent]` checklist → **new** task list | planning | ok→`DISPATCH(all)` · else & `tries<2`→`PLAN_REPORT` |
| `REFINE_REPORT` | `[agent]` NL edit + existing task list → diff `{add, drop, keep}` | planning | ok→`DISPATCH(changed only)` · else & `tries<2`→`REFINE_REPORT` |
| `DISPATCH` | `[sys]` fan out one `TASK[i]` per spec; **reuse cached results for `keep`** | all tasks settled | all `DONE_TASK`/`FAILED_TASK`→`NARRATE` |
| `NARRATE` | `[agent]` prose from `{done, failed}` results | grounding | grounded→`ASSEMBLE` · else & `tries<2`→`NARRATE` |
| `ASSEMBLE` | `[sys]` stitch prose + chart files into the report | artifacts present | → `DELIVER` |

### The per-task sub-machine (what `DISPATCH` fans out)

Each task is the chat inner loop, run **stateless** in its own fresh sandbox, with its
own caps and its own two terminals:

```
TASK[i]:  WRITE_CODE → EXECUTE → ( ENRICH → REPAIR | REDUCE ) → CHECK
          terminals:  DONE_TASK(result, chart_path)  |  FAILED_TASK(reason)
```

`DISPATCH` does not finish until **every** task has reached `DONE_TASK` or `FAILED_TASK`.

### Two consequences this surfaces

- **A task can fail without sinking the report.** `NARRATE` receives
  `{done: [...], failed: [...]}` and must *honestly* write "the revenue-by-region chart
  could not be computed" rather than invent it. Partial failure is a first-class outcome,
  not a crash.
- **Refine is not rebuild.** A refine message ("drop the pie, add a forecast") enters via
  `CLASSIFY → refine → REFINE_REPORT` (not `PLAN_REPORT`). `REFINE_REPORT` emits a
  `{add, drop, keep}` *diff*; `DISPATCH` runs only the `add`ed tasks and **reuses cached
  results** for `keep`. Refining one chart recomputes one chart, not the whole report.

---

## The orchestrator loop (how the table is consumed)

The orchestrator is **generic** — it knows nothing about churn, charts, or any specific
state name. It just drives the table:

```python
state = State(name="CLASSIFY", data=...)
while not terminal(state):
    action  = ACTIONS[state.name]                                   # actions/
    output  = action.run(state, ctx)                                # prompt or [sys] code
    verdict = action.validate(output, ctx)                          # validators/, level per action
    state   = TRANSITIONS[ctx.path][state.name](verdict, state, output)  # transitions/  (this file)
    trace(state, action, verdict)                                   # traces/<session>.jsonl
```

Adding a capability = add one file to `actions/`, register it, add one row above.
Nothing in the orchestrator changes.

---

## Invariants to hold while editing these tables

- **Cap everything.** Every retry edge carries a *named* counter bound (`repair<N`,
  `reduce<2`, `check<2`, …); there is also a global iteration cap and a wall-clock
  timeout on each `sandbox.exec`. No unbounded loops.
- **Same error twice = the feedback didn't land.** A repeated `Verdict.signature` must
  route to `ESCALATE` immediately — never re-run the identical message hoping for a
  different result.
- **Classification belongs to the validator, routing to the transition.** The runtime
  validator decides the `error_kind`; the transition only *branches* on it. A transition
  never inspects a traceback itself.
- **A transition never computes.** It reads a `Verdict` + `State` and returns the next
  `State`. Any checking belongs in `validators/`; any work (including `ENRICH`'s context
  building) belongs in `actions/`.
- **Every path terminates.** From any state there is a route to `DONE` or `FAIL`; the
  escalation ladder always bottoms out at `FAIL`.
- **Partial results are valid.** In the report path, `FAILED_TASK` is a normal terminal;
  `NARRATE` must represent it truthfully, never paper over it.
- **Trace every hop.** A row is only "done" when the `(state, action, verdict)` triple is
  written to the session trace — that file powers debugging and the eval harness.
