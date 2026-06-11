# The Orchestrator — the generic state-machine engine

This is the piece every other directory plugs into. It is deliberately **tiny and
domain-blind**: it turns the crank of `state → action → validate → transition → trace`
and enforces the global caps. It knows nothing about churn, charts, columns, or any
specific state name. All of that lives in `actions/`, `validators/`, and `transitions/`.

> **Action** does the work · **Validation** judges the work · **Transition** decides where
> to go next. The orchestrator only *sequences* those three and records what happened.

Models stay **non-Anthropic** (default: Gemini Flash; `strong` tier only on escalation).

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
    sandbox: Sandbox                # PERSISTENT across turns in chat; FRESH per task in report
    models: dict                    # {"cheap": GeminiFlash(...), "strong": <stronger model>}
    summary: str = ""               # rolling chat summary — never the full history
    trace_path: str = ""            # traces/<session>.jsonl
    data: dict = field(default_factory=dict)   # scratch: last plan, last code, last verdict, ...

# Every action — [agent] or [sys] — exposes exactly this to the engine:
class Action(Protocol):
    NAME: str
    async def run(self, state: "State", ctx: Ctx) -> object: ...   # produce output
    def validate(self, output, ctx: Ctx) -> "Verdict": ...         # judge output

# A transition is a PURE function: read the verdict + state, RETURN the next state.
Transition = Callable[["Verdict", "State", object], "State"]
TRANSITIONS: dict[str, dict[str, Transition]]      # TRANSITIONS[ctx.path][state.name]
```

The README's `SYSTEM / MODEL_TIER / build_messages / parse` are the **internals of an
agent action**. A shared adapter turns them into the uniform `run()` the engine calls, so
the engine treats `[agent]` and `[sys]` identically:

```python
# The ONLY place a model is ever called. Shared by every [agent] action.
async def agent_run(action, state, ctx) -> object:
    tier = "strong" if state.tier == "strong" else getattr(action, "MODEL_TIER", "cheap")
    messages = action.build_messages(ctx)        # SYSTEM + (profile + the one input)
    raw      = await ctx.models[tier].complete(messages)
    return action.parse(raw)                      # → structured object, never raw prose

# A [sys] action (execute, enrich, dispatch, assemble) simply IS run(): no model, no tier.
```

---

## 3. The engine — `run_machine`

The entire orchestrator. ~25 lines. The chat loop **and** each report task run through it.

```python
TERMINAL = {"DONE", "FAIL", "AWAIT"}     # AWAIT = ASK emitted a question; hand back to the user

async def run_machine(state: State, ctx: Ctx, max_hops: int = 40) -> State:
    table = TRANSITIONS[ctx.path]
    for _ in range(max_hops):                          # global safety cap — no infinite loops
        if state.name in TERMINAL:
            return state

        action  = ACTIONS[state.name]                  # actions/  (resolved by name)
        output  = await action.run(state, ctx)         # [agent] call OR [sys] code
        verdict = action.validate(output, ctx)         # validators/  (level chosen by the action)

        trace(ctx, state, action.NAME, verdict, output)    # write BEFORE transition — see §6

        state = table[state.name](verdict, state, output)  # transitions/  (this decides next)

    return State(name="FAIL", data={"reason": f"hit max_hops={max_hops}"})
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
    c = state.counters
    if verdict.ok:                                              # clean
        return State("CHECK", state.data, reset(c, "repair", "reduce"))
    if verdict.signature == state.data.get("last_sig"):         # same error twice
        return State("ESCALATE", state.data, c, state.esc_level, state.tier)
    state.data["last_sig"] = verdict.signature
    if verdict.error_kind == "RESOURCE" and c.get("reduce", 0) < 2:
        return State("REDUCE", state.data, bump(c, "reduce"))
    if c.get("repair", 0) < N:
        return State("ENRICH", state.data, bump(c, "repair"))
    return State("ESCALATE", state.data, c, state.esc_level, state.tier)
```

`reset` and `bump` are two-line helpers over the `counters` dict.

---

## 5. The report path reuses the engine — it does not fork it

`DISPATCH` is a `[sys]` action whose `run()` calls **`run_machine` again**, once per task,
in parallel, each with a *fresh* sandbox and `ctx.path="task"`:

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
transition table `ctx.path` selects and whether the sandbox is shared or fresh. The
"report is the same engine" claim from the README is now literally true in code.

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

- **Async, not sync.** Report fan-out needs `asyncio.gather`; chat model calls are IO-bound
  anyway. Cheap now, painful to retrofit.
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
