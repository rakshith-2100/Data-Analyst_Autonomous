# The Orchestrator — the generic state-machine engine

This is the piece every other directory plugs into. It is deliberately **tiny and
domain-blind**: it turns the crank of `state → action → validate → transition → trace`
and enforces the global caps. It knows nothing about churn, charts, columns, or any
specific state name. All of that lives in `actions/`, `validators/`, and `transitions/`.

> **Action** does the work · **Validation** judges the work · **Transition** decides where
> to go next. The orchestrator only *sequences* those three and records what happened.

Models are **OpenAI GPT** (default: the cheap GPT tier, e.g. `gpt-4.1-mini`; the `strong`
tier, e.g. `gpt-4.1`, only on escalation).

> **Status.** The engine, the `chat` path, and tracing are implemented and live. The
> `report`/`task` fan-out in §5 is the **designed** target — those transition tables and
> their actions (`DISPATCH`, `NARRATE`, …) are still stubs. See
> [architecture.md](architecture.md) for the implemented-vs-planned split and the
> low-level rationale for not using LangGraph or AutoGen.

---

## 1. What it owns vs. what it must never do

```
The orchestrator OWNS:            The orchestrator NEVER:
  • the loop                        • knows a state name's meaning
  • picking the action by name      • parses a traceback
  • calling validate                • decides a verdict      (→ validators/)
  • dispatching the transition      • routes / branches      (→ transitions/)
  • enforcing the global cap        • does domain work       (→ actions/)
  • writing the trace               • imports a state name as a literal
  • model-tier selection
```

Litmus test: if you can `grep` a domain state name (e.g. `"CHECK"`) inside
`orchestrator.py`, domain logic has leaked into the engine. The only strings the engine
knows are the members of `TERMINAL`.

---

## 2. The contracts it depends on

```python
# Assembled once per run. The ONLY object actions/validators/transitions receive.
@dataclass
class Ctx:
    path: str                       # "chat" | "report" | "task" → selects the transition table
    profile: Profile                # source of truth for columns
    question: str                   # or task.instruction in the report/task paths
    sandbox: Sandbox                # one Sandbox per chat session; FRESH per task in report
    models: Models                  # one wrapper over the OpenAI client; the tiers live inside it
    summary: str = ""               # rolling chat summary — never the full history
    trace_path: str = ""            # traces/<session>.jsonl
    data: dict = field(default_factory=dict)   # scratch: last plan, last code, last verdict, ...

# Every action — [agent] or [sys] — exposes exactly this to the engine:
class Action(Protocol):
    NAME: str
    def run(self, state: "State", ctx: Ctx) -> object: ...   # produce output (sync [sys] OR async [agent])
    def validate(self, output, ctx: Ctx) -> "Verdict": ...   # judge output

# A transition is a PURE function: read the verdict + state, RETURN the next state.
Transition = Callable[["Verdict", "State", object], "State"]
TRANSITIONS: dict[str, dict[str, Transition]]      # TRANSITIONS[ctx.path][state.name]
```

The README's `SYSTEM / MODEL_TIER / build_messages / parse` are the **internals of an
agent action**. A shared adapter turns them into the uniform `run()` the engine calls, so
the engine treats `[agent]` and `[sys]` identically:

```python
# actions/base.py — the ONLY place a model is ever called. Shared by every [agent] action.
def agent_run(action_name, build_messages, parse, state, ctx, *, model_tier="cheap", json_mode=False):
    tier     = "strong" if getattr(state, "tier", "cheap") == "strong" else model_tier
    messages = build_messages(ctx)               # SYSTEM + (profile + the one input)
    raw      = ctx.models.complete(messages, tier=tier, action=action_name.lower(), json_mode=json_mode)
    return parse(raw)                            # → structured object, never raw prose

# A [sys] action (execute, enrich, dispatch, assemble) simply IS run(): no model, no tier.
# agent_run is synchronous; run_machine wraps every run() in _maybe_await (§3), so an action
# may be sync ([sys]) or async ([agent]) and the engine treats them identically.
```

---

## 3. The engine — `run_machine`

The entire orchestrator. ~25 lines. The chat loop **and** each report task run through it.

```python
TERMINAL = {"DONE", "FAIL", "AWAIT"}     # AWAIT = ASK emitted a question; hand back to the user

async def run_machine(state: State, ctx: Ctx, *, max_hops: int = 40) -> State:
    table = TRANSITIONS[ctx.path]
    for _ in range(max_hops):                              # global safety cap — no infinite loops
        if state.name in TERMINAL:
            return state

        action  = ACTIONS[state.name]                      # actions/  (resolved by name)
        output  = await _maybe_await(action.run(state, ctx))  # [agent] call OR [sys] code (sync or async)
        verdict = action.validate(output, ctx)             # validators/  (level chosen by the action)

        trace(ctx, state, action.NAME, verdict, output)        # write BEFORE transition — see §6

        state = table[state.name](verdict, state, output)      # transitions/  (this decides next)

    return State(name="FAIL", data={**state.data, "reason": f"hit max_hops={max_hops}"})
```

Everything hard is pushed into the plug-ins; the engine just sequences and enforces the
one global cap.

---

## 4. Caps and counters — three layers, each in its right place

| Cap | Lives in | Why there |
|---|---|---|
| Per-state retry (`repair<N`, `check<2`, `reduce<2`, …) | **transitions** | the transition builds the next `State` and bumps its named counter |
| Global hop cap (`max_hops`) | **engine** | last-resort backstop against a routing bug |
| Wall-clock timeout | **`sandbox.exec`** | only the sandbox can time-box arbitrary code |

A transition incrementing a counter does **not** break "a transition never computes": the
*judging* already happened in the validator. The transition only reads that verdict and
assembles the next `State` (name + counters + `esc_level` + `tier`).

```python
# transitions/chat.py — the EXECUTE row, in full. Reads exactly like the table row.
def from_execute(verdict, state, output):
    if verdict.ok:                                              # clean
        return goto("CHECK", state, counters=reset(state, "repair", "reduce"))
    data = dict(state.data)
    sig = verdict.signature
    if sig and sig == data.get("last_sig"):                     # same error twice
        return goto("ESCALATE", state, data=data)
    data["last_sig"] = sig
    if verdict.error_kind == "RESOURCE" and count(state, "reduce") < 2:
        return goto("REDUCE", state, data=data, counters=bump(state, "reduce"))
    if count(state, "repair") < REPAIR_CAP:                     # REPAIR_CAP = 3
        return goto("ENRICH", state, data=data, counters=bump(state, "repair"))
    return goto("ESCALATE", state, data=data)
```

`goto`, `bump`, `reset`, and `count` are the construction-only helpers in
`transitions/util.py`: `goto` builds the next `State` (preserving `data`/`counters`/
`esc_level`/`tier` unless overridden); `bump`/`reset`/`count` manage the named counters dict.

---

## 5. The report path reuses the engine — it does not fork it

> **Designed, not yet wired.** This is the intended shape; `actions/dispatch.py` and the
> `report`/`task` transition tables are still stubs. It is documented here because it is
> what the engine's `ctx.path` seam exists to enable. See the
> [README's next-improvements](../README.md#next-improvements).

`DISPATCH` is a `[sys]` action whose `run()` will call **`run_machine` again**, once per
task, in parallel, each with a *fresh* sandbox and `ctx.path="task"`:

```python
# actions/dispatch.py — [sys], no prompt
async def run(state, ctx) -> dict:
    tasks  = state.data["tasks"]                       # from PLAN_REPORT / REFINE_REPORT
    cached = state.data.get("keep_results", {})        # incremental refine: reuse unchanged tasks

    async def one(task):
        sub = Ctx(path="task", profile=ctx.profile, question=task.instruction,
                  sandbox=Sandbox(), models=ctx.models, trace_path=ctx.trace_path)  # FRESH sandbox
        return await run_machine(State("WRITE_CODE", {"task": task}), sub)          # → DONE_TASK | FAILED_TASK

    fresh   = await asyncio.gather(*(one(t) for t in tasks if t.id not in cached))
    settled = list(cached.values()) + list(fresh)
    return {"done":   [s for s in settled if s.name == "DONE_TASK"],
            "failed": [s for s in settled if s.name == "FAILED_TASK"]}
```

**One engine, three entry points** (`chat`, `report`, `task`) — differing only by which
transition table `ctx.path` selects and whether the sandbox is shared or fresh. Today only
`chat` is wired; `report`/`task` reuse the *same* `run_machine`, so bringing them online is
adding their tables and actions, not changing the engine.

---

## 6. Tracing — from day one

One append-only JSONL line per hop, written **before** the transition fires, so a crash
still leaves a record of what was being decided:

```python
def trace(ctx, state, action_name, verdict, output):
    append_jsonl(ctx.trace_path, {
        "state":    state.name,
        "action":   action_name,
        "verdict":  asdict(verdict),
        "tier":     state.tier,
        "counters": state.counters,
        "output":   preview(output),       # truncate code / results
    })
```

This is the same artifact `eval/run_eval.py` replays — one file, two uses (debugging and
the eval harness).

---

## 7. Non-obvious decisions worth pinning

- **Async-ready, sync today.** `run_machine` is async and wraps every `run()` in
  `_maybe_await`, so an action may be sync or async. The model calls themselves are
  currently synchronous (`agent_run` → `Models.complete`); the async seam is kept because
  the planned report fan-out needs `asyncio.gather`, and that is painful to retrofit later.
- **`AWAIT` is a real terminal.** In a web app each user message = one `run_machine` call.
  `ASK` emits a question and routes to `AWAIT`; the server persists `ctx` (sandbox +
  summary) and resumes at `CLASSIFY` on the next message. That is how "wait for reply"
  works without threads.
- **Tier override rides on `State`, not a global.** `ESCALATE` flips `state.tier="strong"`;
  the next `agent_run` picks the strong client automatically. No special re-entry path.
- **The engine imports no state name.** The only strings it knows are in `TERMINAL`.
- **Trace before transition.** The record of "what we were deciding" must survive a crash
  in the transition itself.

---

## 8. How the engine consumes the plug-ins (the whole picture)

```
                ┌──────────────── run_machine (this file) ────────────────┐
   State ──────▶│  ACTIONS[name].run ──▶ output                           │
                │            │                                            │
                │            ▼                                            │
                │  ACTIONS[name].validate ──▶ Verdict                     │
                │            │                                            │
                │            ▼                                            │
                │  trace(...)                                             │
                │            │                                            │
                │            ▼                                            │
                │  TRANSITIONS[path][name](verdict, state, output) ──▶ next State
                └─────────────────────────────────────────────────────────┘
                             │
                             ▼  (loops until DONE / FAIL / AWAIT)

Adding a capability = add one actions/ file + one transitions/ row. The engine is untouched.
```
