# Transition Tables — the state-machine routers

This is the routing layer of the architecture, pulled out on its own so it's easy to
review and edit. It is the **planner you write by hand**: every row is a deterministic
`if/else` that reads a validation *verdict* and decides the next state. The model is
never asked "what should I do next" — that answer lives here.

> **Action** does the work (`actions/`). **Validation** judges the work (`validators/`).
> **Transition** (this file) decides where to go next. Three different things.

Legend:
- `[agent]` = a prompt-driven model call · `[sys]` = plain code, **zero tokens**
- `tries` = a per-state retry counter · `N` = the repair cap (small, e.g. 2–3)
- Validation level = the cheapest check that can catch *this* action's failure mode

---

## Chat path  (`transitions/chat.py`)

One persistent-state loop. The sandbox namespace survives across turns, so a follow-up
like "now show it as a pie" can build on the previous result.

| State | Action | Validation | Transition (verdict → next state) |
|---|---|---|---|
| `CLASSIFY` | `[agent]` label the message | schema (enum) | `question`→`PLAN_STEP` · `unclear`→`ASK` · `refine`→`PLAN_REPORT` · `out_of_scope`→`RESPOND` |
| `PLAN_STEP` | `[agent]` pick columns + op, 1-line plan, **no code** | planning | ok→`WRITE_CODE` · bad column & `tries<2`→`PLAN_STEP` · ambiguous→`ASK` |
| `WRITE_CODE` | `[agent]` one pandas/matplotlib cell from the plan | syntax | compiles→`EXECUTE` · else & `tries<2`→`WRITE_CODE` |
| `EXECUTE` | `[sys]` run cell in the sandbox | runtime | clean→`CHECK` · exception→`REPAIR` · timeout/memory→`REDUCE` |
| `REPAIR` | `[agent]` fix from the **enriched** traceback | syntax | `tries<N`→`EXECUTE` · else→`ESCALATE` |
| `REDUCE` | `[agent]` rewrite to sample/chunk the data | planning | `tries<2`→`EXECUTE` · else→`ESCALATE` |
| `CHECK` | `[agent]` does the result answer the question? | sanity | yes→`COMPOSE` · no & `tries<2`→`PLAN_STEP` · else→`ESCALATE` |
| `COMPOSE` | `[agent]` write the answer over the result | grounding | grounded→`DELIVER` · else & `tries<2`→`COMPOSE` |
| `ASK` | `[agent]` one clarifying question | schema | → wait for reply → `CLASSIFY` |
| `RESPOND` | `[agent]` short out-of-scope reply | — | → `DONE` |
| `ESCALATE` | `[sys]` swap to a stronger model, or bail | — | budget left→`EXECUTE` (strong model) · else→`FAIL` |
| `DELIVER` | `[sys]` stream answer + charts to the user | — | → `DONE`; next message → `CLASSIFY` |
| `FAIL` | `[sys]` honest "couldn't compute X" message | — | → `DONE` |

**Terminal states:** `DONE`, `FAIL`.

---

## Report path  (`transitions/report.py`)

Same engine, second entry point. `PLAN_REPORT` mirrors `PLAN_STEP` (same planning
validation, same retry-on-bad-column) but emits **N** task specs instead of one. Each
task then runs the **exact same** `WRITE_CODE → EXECUTE → REPAIR → CHECK` actions —
in parallel and **stateless** (fresh sandbox per task).

| State | Action | Validation | Transition (verdict → next state) |
|---|---|---|---|
| `PLAN_REPORT` | `[agent]` checklist → task list | planning | ok→`DISPATCH` · else & `tries<2`→`PLAN_REPORT` |
| `DISPATCH` | `[sys]` fan out; **each task runs `WRITE_CODE→EXECUTE→REPAIR→CHECK` in isolation** | all tasks terminal | all settled→`NARRATE` |
| `NARRATE` | `[agent]` report prose from completed results | grounding | grounded→`ASSEMBLE` · else & `tries<2`→`NARRATE` |
| `ASSEMBLE` | `[sys]` stitch prose + chart files into the report | artifacts present | → `DELIVER` |

After `DELIVER`, a refine message ("drop the pie, add a forecast") re-enters via
`CLASSIFY` → `refine` → `PLAN_REPORT`, so reports update in place.

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

- **Cap everything.** Every retry edge must carry a `tries` bound; there is also a
  global iteration cap and a wall-clock timeout on each `sandbox.exec`. No unbounded loops.
- **Same error twice = the feedback didn't land.** A repeated identical verdict must
  *escalate* (enrich feedback → change strategy → stronger model → bail), never re-run
  the identical message.
- **A transition never computes.** It only reads a `Verdict` and returns the next
  `State`. Any actual checking belongs in `validators/`; any work belongs in `actions/`.
- **Every path terminates.** From any state there is a route to `DONE` or `FAIL`.
- **Trace every hop.** A row is only "done" when the `(state, action, verdict)` triple
  is written to the session trace — that file powers debugging and the eval harness.
