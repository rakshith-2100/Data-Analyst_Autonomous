# Architecture

This document explains, in depth, how the CSV Data Analyst is built — and, at a low
level, **why routing is a hand-written state machine instead of LangGraph or AutoGen.**

It assumes you've read the [README](../README.md) overview. Where the README says *what*,
this says *how* and *why*.

- [1. One idea](#1-one-idea)
- [2. The four roles](#2-the-four-roles)
- [3. The engine (`run_machine`)](#3-the-engine-run_machine)
- [4. What flows through the machine: `State` and `Ctx`](#4-what-flows-through-the-machine-state-and-ctx)
- [5. The chat state machine](#5-the-chat-state-machine)
- [6. Control: counters, the signature loop-breaker, the escalation ladder](#6-control-counters-the-signature-loop-breaker-the-escalation-ladder)
- [7. Actions: `[agent]` vs `[sys]`](#7-actions-agent-vs-sys)
- [8. Validators: the ladder](#8-validators-the-ladder)
- [9. The sandbox](#9-the-sandbox)
- [10. Models and tiers](#10-models-and-tiers)
- [11. Sessions, persistence, and the API](#11-sessions-persistence-and-the-api)
- [12. The frontend](#12-the-frontend)
- [13. Why not LangGraph (for routing)](#13-why-not-langgraph-for-routing)
- [14. Why not AutoGen (for routing)](#14-why-not-autogen-for-routing)
- [15. The honest trade-offs](#15-the-honest-trade-offs)

---

## 1. One idea

The model never does "the analysis." It only ever performs one tiny, bounded task —
classify a message, plan one step, write one code cell, write two sentences. Everything
else is a deterministic harness around those calls:

> **Action** does the work · **Validator** judges the work · **Transition** decides where
> to go next · **Orchestrator** only sequences those three and records what happened.

Those four roles live in four different places and never bleed into each other. That
separation is the whole design. It is what makes a *cheap* model reliable, and it is the
specific thing LangGraph and AutoGen do **not** enforce (§13, §14).

```
data_analyst/src/
  orchestrator.py        # the generic engine (~25 lines) — domain-blind
  core.py                # State, Verdict, ExecResult, Task  (pure dataclasses)
  actions/               # do the work — one module per state
    base.py              # agent_run: the single model-call adapter
    __init__.py          # ACTIONS = {name -> module}
    classify.py plan_step.py write_code.py execute.py enrich.py
    repair.py reduce.py check.py compose.py ask.py respond.py ...
  validators/            # judge the work — the validation ladder
    schema.py planning.py syntax.py runtime.py sanity.py grounding.py
  transitions/           # decide the next state — pure routing tables
    __init__.py          # TRANSITIONS = {"chat"|"report"|"task" -> table}
    chat.py util.py
  models.py              # the one OpenAI client (cheap / strong tiers)
  sandbox.py             # subprocess code execution with a wall-clock timeout
  chat.py                # ChatSession: memory + AWAIT-resume over run_machine
  api.py db.py           # FastAPI + SQLite persistence
```

---

## 2. The four roles

| Role | Lives in | Signature | May it call a model? | May it route? |
|---|---|---|---|---|
| **Action** | `actions/<name>.py` | `run(state, ctx)` | yes (`[agent]`) or no (`[sys]`) | never |
| **Validator** | `validators/<level>.py` | `validate(output, ctx) -> Verdict` | only `sanity`/`grounding` | never |
| **Transition** | `transitions/chat.py` | `(verdict, state, output) -> State` | never | **only this** |
| **Orchestrator** | `orchestrator.py` | `run_machine(state, ctx)` | never | never (just calls the table) |

The contract is strict and one-directional:

- A **validator never routes.** It returns a `Verdict` (a judgment), not a next state.
- A **transition never computes.** It reads the `Verdict` + counters and returns the next
  `State`. It performs no work and calls no model.
- The **engine knows no domain.** `orchestrator.py` imports zero state names except the
  terminal set `{DONE, FAIL, AWAIT}`. It cannot tell churn from charts.

Adding a capability = add one `actions/` module, register it in `ACTIONS`, and add one row
to the transition table. Nothing else changes.

---

## 3. The engine (`run_machine`)

The entire control model is this loop (`data_analyst/src/orchestrator.py:59-72`):

```python
for _ in range(max_hops):
    if terminal(state):
        return state

    action  = actions[state.name]                        # actions/  (resolved by name)
    output  = await _maybe_await(action.run(state, ctx))  # [agent] call OR [sys] code
    verdict = action.validate(output, ctx)               # validators/ (level per action)

    trace(ctx, state, getattr(action, "NAME", state.name), verdict, output)

    state   = table[state.name](verdict, state, output)  # transitions/ (decides next)
```

Five things worth noticing:

1. **Nodes are resolved by string name** from a dict registry: `actions[state.name]`
   (`actions/__init__.py` builds `ACTIONS = {m.NAME: m for m in _MODULES}`). There is no
   graph object — just a name → module map.
2. **Edges are the transition table:** `table = TRANSITIONS[ctx.path]`
   (`orchestrator.py:57`). `ctx.path` (`"chat"`/`"report"`/`"task"`) selects which table —
   this is how "one engine, many flows" works.
3. **`_maybe_await`** (`orchestrator.py:93-97`) lets `run` be sync (`[sys]` code) or async
   (`[agent]` model call) — the engine treats both identically.
4. **The trace is written *before* the transition fires** (`orchestrator.py:67`,
   `75-90`), so a crash mid-routing still leaves a record of what was being decided. One
   append-only JSONL line per hop; this is also the eval-replay artifact.
5. **One global cap.** `max_hops=40` is the engine's *only* safety limit (line 71 turns a
   runaway into a clean `FAIL`). Per-state retry caps live in transitions; the wall-clock
   timeout lives in the sandbox. Each cap lives where it belongs.

That's the whole engine. No compilation step, no channels, no reducers, no scheduler.

---

## 4. What flows through the machine: `State` and `Ctx`

Two objects are threaded through every hop.

**`State`** (`core.py:29-37`) — *where we are*, plus retry/escalation bookkeeping:

```python
@dataclass
class State:
    name: str                     # current node, e.g. "EXECUTE"
    data: dict                    # scratch carried between states
    counters: dict                # named retry counters: plan/code/repair/reduce/check/compose
    esc_level: int = 0            # escalation rung: 0 none | 1 restrategized | 2 strong model
    tier: str = "cheap"           # cheap | strong  (ESCALATE may flip to strong)
```

**`Ctx`** (`orchestrator.py:32-42`) — assembled once per run; the only object actions,
validators, and transitions receive:

```python
@dataclass
class Ctx:
    path: str                     # "chat" | "report" | "task" -> selects the transition table
    profile: Profile | None       # the dataset profile (column names are the source of truth)
    question: str                 # the user's question (or a task instruction)
    sandbox: Sandbox | None        # persistent in chat, fresh per task in report
    models: Models | None
    summary: str = ""             # rolling chat summary — never the full history
    trace_path: str = ""
    data: dict = field(default_factory=dict)  # cross-action scratch
```

State is passed two ways, both **explicit**:

- **`goto()`** (`transitions/util.py:11-18`) constructs the next `State`, preserving
  `data` / `counters` / `esc_level` / `tier` unless an argument overrides them. Nothing
  merges behind your back.
- **`ctx.data` mutation** — actions stash outputs for downstream actions:
  `PLAN_STEP` writes `ctx.data["plan"]`, `WRITE_CODE` reads it and writes
  `ctx.data["code"]`, `EXECUTE` runs it and writes `ctx.data["exec_result"]`, `COMPOSE`
  reads the result and writes `ctx.data["answer"]`.

There is no reducer, no channel, no implicit merge. If a value moved, a line of code moved
it. (This is a deliberate contrast with LangGraph — see §13.)

---

## 5. The chat state machine

`transitions/chat.py` is the full chat routing table. Every function is pure: it reads the
`Verdict` + counters and returns the next `State`. The happy path:

```
CLASSIFY → PLAN_STEP → WRITE_CODE → EXECUTE → CHECK → COMPOSE → DELIVER → DONE
```

with error branches into `ENRICH → REPAIR`, `REDUCE`, and a two-rung `ESCALATE` ladder.
The canonical example is the `EXECUTE` row (`transitions/chat.py:41-53`):

```python
def from_execute(verdict, state, output):
    if verdict.ok:
        return goto("CHECK", state, counters=reset(state, "repair", "reduce"))
    data = dict(state.data)
    sig = verdict.signature
    if sig and sig == data.get("last_sig"):        # same error twice -> feedback didn't land
        return goto("ESCALATE", state, data=data)
    data["last_sig"] = sig
    if verdict.error_kind == "RESOURCE" and count(state, "reduce") < 2:
        return goto("REDUCE", state, data=data, counters=bump(state, "reduce"))
    if count(state, "repair") < REPAIR_CAP:         # REPAIR_CAP = 3
        return goto("ENRICH", state, data=data, counters=bump(state, "repair"))
    return goto("ESCALATE", state, data=data)
```

Every branch in the system is plain Python `if` over a small, enumerable `Verdict`. You can
read the entire control flow of the agent by reading one file — no graph to render, no
framework semantics to simulate in your head.

| State | Action kind | Validator | Routes to |
|---|---|---|---|
| `CLASSIFY` | `[agent]` | schema | `PLAN_STEP` · `ASK` · `RESPOND` |
| `PLAN_STEP` | `[agent]` | planning | `WRITE_CODE` · retry · `ASK` |
| `WRITE_CODE` | `[agent]` | syntax | `EXECUTE` · retry · `ESCALATE` |
| `EXECUTE` | `[sys]` | runtime (classifies `error_kind` + `signature`) | `CHECK` · `REDUCE` · `ENRICH` · `ESCALATE` |
| `ENRICH` | `[sys]` | — | `REPAIR` |
| `REPAIR` | `[agent]` | syntax | `EXECUTE` · retry · `ESCALATE` |
| `REDUCE` | `[agent]` | planning | `EXECUTE` · `ESCALATE` |
| `CHECK` | `[agent]` | sanity | `COMPOSE` · re-plan · `ESCALATE` |
| `COMPOSE` | `[agent]` | grounding | `DELIVER` · retry · `FAIL` |
| `ASK` | `[agent]` | schema | `AWAIT` (hand back to user) |
| `RESPOND` | `[agent]` | — | `DONE` |
| `ESCALATE` | `[sys]` | — | re-plan · strong model · `FAIL` |
| `DELIVER` / `FAIL` | `[sys]` | — | `DONE` |

> The `report` and `task` tables exist as `ctx.path` targets but are not yet wired — see
> [next improvements](../README.md#next-improvements).

---

## 6. Control: counters, the signature loop-breaker, the escalation ladder

Three independent mechanisms keep a cheap model from spinning — each at the right layer.

**Named per-state counters.** `counters` is a dict keyed by failure mode
(`transitions/util.py`: `bump`, `reset`, `count`). `repair < 3`, `code < 2`, `reduce < 2`,
`check < 2` — each failure mode gets *its own* budget instead of one global retry count, so
exhausting repairs doesn't eat the planning retries. A successful `EXECUTE` resets the
`repair`/`reduce` counters, so a later, unrelated error gets a fresh budget.

**The signature loop-breaker.** `validators/runtime.py` classifies an `ExecResult` into a
closed set of `error_kind`s (`MISSING_COLUMN` / `BAD_VALUE` / `RESOURCE` / `NAME_OR_LOGIC`
/ `OTHER`) **and** computes `signature = md5(exception_type + "cell.py:line")`. The
transition compares the new signature to `data["last_sig"]`: **the same error twice means
the repair feedback didn't land**, so it escalates instead of burning the rest of the
repair budget on an identical failure. This is *semantic* progress detection — a raw retry
counter cannot express "am I actually getting somewhere."

**The escalation ladder** (`transitions/chat.py:101-108`) rides on `State`, not on a global
flag:

```python
def from_escalate(verdict, state, output):
    if state.esc_level == 0:                       # rung 1: change strategy
        return goto("PLAN_STEP", state, esc_level=1, counters=reset(state, "code", "repair", "reduce"))
    if state.esc_level == 1:                       # rung 2: stronger model, same plan
        return goto("WRITE_CODE", state, esc_level=2, tier="strong", counters=reset(state, "code", "repair"))
    return goto("FAIL", state, data={**state.data, "reason": "exhausted recovery options"})
```

- rung 0 → re-strategize (back to `PLAN_STEP`)
- rung 1 → escalate the *model* (back to `WRITE_CODE` with `tier="strong"`; the next
  `agent_run` automatically picks the strong client — §7/§10)
- rung 2 → give up honestly (`FAIL`)

Because the rung and the tier live on the state object, they survive an `AWAIT`/resume for
free, and the engine stays oblivious to them.

---

## 7. Actions: `[agent]` vs `[sys]`

Every action module exposes the same two-method interface — `run(state, ctx)` and
`validate(output, ctx)` — so the engine treats them all identically. They come in two
flavors:

- **`[agent]`** — a model call. It supplies only `build_messages(ctx)` (a SYSTEM prompt
  from `prompts/actions/<name>.md` + a USER message built from the profile/question/plan)
  and `parse(raw)`. Everything else is shared.
- **`[sys]`** — plain code, zero tokens. `EXECUTE` runs the sandbox, `ENRICH` builds
  targeted error context, `ESCALATE` picks the next recovery rung.

Every model call in the system funnels through **one adapter**, `agent_run`
(`actions/base.py:13-19`):

```python
def agent_run(action_name, build_messages, parse, state, ctx, *, model_tier="cheap", json_mode=False):
    tier = "strong" if getattr(state, "tier", "cheap") == "strong" else model_tier
    messages = build_messages(ctx)
    raw = ctx.models.complete(messages, tier=tier, action=action_name.lower(), json_mode=json_mode)
    return parse(raw)
```

This single chokepoint is where the tier decision (`state.tier` overrides the action
default — that's how `ESCALATE` upgrades the model), the prompt assembly, and the parse all
happen. Together with `models.py`, it is the *only* code that touches the SDK.

Three prompt rules make cheap models reliable:

1. **Single responsibility** — one action does exactly one thing; "do X then Y" is two
   actions.
2. **Minimal context** — an action sees the profile + its one input, never the full chat
   history (chat keeps only a short rolling `summary`; report tasks are fully stateless).
3. **Structured output, always** — strict JSON or a single fenced code block, validated
   before anything downstream touches it.

---

## 8. Validators: the ladder

`Verdict` (`core.py:19-27`) is the judgment a validator returns and a transition reads:
`ok`, `level`, `reason`, and — for runtime only — `error_kind` and `signature`.

Each action picks the **cheapest validator that catches its failure mode**:

| Level | File | Cost | Catches |
|---|---|---|---|
| schema | `validators/schema.py` | free | output isn't the expected JSON shape / enum |
| planning | `validators/planning.py` | free | references a column not in the profile |
| syntax | `validators/syntax.py` | free (`compile()` + import allowlist) | won't parse / banned import |
| runtime | `validators/runtime.py` | free | raised / timed out; **classifies `error_kind` + `signature`** |
| sanity | `validators/sanity.py` | 1 model call | ran clean but answers the wrong question |
| grounding | `validators/grounding.py` | code or 1 model call | a stated number isn't in the result |

Four of six levels cost **zero model calls**. `syntax.py` enforces an import allowlist
(`pandas` / `numpy` / `matplotlib`), so `import os` is rejected *before* the sandbox ever
runs. `grounding.py` checks every substantive number in the composed answer traces back to
the computed result — the anti-hallucination backstop.

---

## 9. The sandbox

`sandbox.py` runs each model-written cell in an **isolated subprocess** (`subprocess.run`,
line 66) with `df` preloaded from the CSV, a fresh temp cwd, matplotlib forced to the
headless `Agg` backend, captured stdout, and a wall-clock `timeout` (default 15s — kills
runaway loops). Charts written to `./out/` are returned as artifacts. The threat model is a
*buggy* (not malicious) LLM; the subprocess can be swapped for Docker/e2b without touching
callers. The single result shape is `ExecResult{stdout, error, artifacts}` (`core.py:39-44`)
— the one thing `runtime.py` classifies.

---

## 10. Models and tiers

`models.py` is the only place a model is called. A single `Models` wrapper exposes two
tiers from `.env`:

- `OPENAI_MODEL_CHEAP` (default `gpt-4.1-mini`) — used for everything.
- `OPENAI_MODEL_STRONG` (default `gpt-4.1`) — used **only** when `ESCALATE` flips
  `state.tier="strong"`.

`complete()` supports `json_mode` (`response_format={"type":"json_object"}`) and
`temperature=0.0`, and logs the full prompt+response to `logs/prompts_response/<action>.log`
on every call. The provider is **OpenAI GPT** — the axis that matters here is
structured-output reliability, not chat IQ, because every action returns strict JSON or a
single code block.

---

## 11. Sessions, persistence, and the API

`chat.py`'s `ChatSession` adds two things on top of `run_machine`:

- **Conversation memory** — a short rolling `summary()` (last few turns) fed into prompts,
  so "now show it as a pie" resolves against the prior turn.
- **`AWAIT` resume** — `ASK` ends a turn at the terminal `AWAIT` state. `ChatSession`
  stores the pending clarification and, on the next message, folds the reply back into the
  original question (`_question_for`) and re-runs `run_machine` from `CLASSIFY`. Each user
  message = exactly one `run_machine` call; the clarify→answer loop closes across turns with
  no threads.

`api.py` (FastAPI) wraps the chat path and persists sessions + messages in SQLite
(`data/app.db`); chart/table artifacts are copied to `data/artifacts/<sid>/` so they
survive restarts. After a restart a session is **rehydrated** from the DB on first request
(re-profiling the stored CSV, rebuilding conversation memory). Endpoints:

| Method & path | Purpose |
|---|---|
| `POST /sessions` · `POST /sessions/sample` | Upload a CSV (or use the bundled sample) → profile → open a session |
| `GET /sessions` | List a user's past chats (scoped by `X-User-Id`) |
| `POST /sessions/{sid}/chat` | **Run one turn through the state machine** → `{state, answer, images, tables}` |
| `GET /sessions/{sid}/messages` · `GET /sessions/{sid}` | Stored history / profile |
| `GET /sessions/{sid}/artifacts/{name}` | Serve a chart PNG or table CSV |

The full chain: **frontend `api.ts` → `api.py` → `ChatSession.ask` → `run_machine` →
actions (model via `Models` / sandbox subprocess) → validators → transitions → loop until
`DONE`/`FAIL`/`AWAIT`.**

---

## 12. The frontend

`app/` is React 19 + TypeScript + Vite, no state-management library — plain hooks.
`App.tsx` uses hash routing (`#/` = upload landing, `#/c/<sid>` = a conversation) so chats
are deep-linkable and the back button works. `api.ts` is the backend client (base
`http://127.0.0.1:8000`, overridable via `VITE_API`); it mints a stable per-browser
`userId` in `localStorage` and sends it as `X-User-Id` to scope past chats. `ChatView`
drives a turn: append a user message + a pending assistant bubble, call `sendChat`, then
replace the bubble with the answer plus server-rendered chart PNGs and parsed CSV tables.

---

## 13. Why not LangGraph (for routing)

LangGraph is a real option for exactly this shape of problem, and the engine here is
deliberately *LangGraph-like*. The decision not to use it is about **routing specifically**,
at a low level. Four concrete reasons:

**(a) A LangGraph node is one function that does work *and* judges *and* prepares routing.**
The framework gives you `add_node` / `add_conditional_edge`, but nothing **enforces** the
action/validator/transition split. In practice routing logic, the model call, and result
validation accumulate inside a single node function. This project makes the split
structural: a validator that tries to route has nowhere to put the next-state — it can only
return a `Verdict`. The separation is enforced by the shape of the interfaces, not by
discipline. *(See the discussion in the project history: you can decompose a LangGraph
graph into smaller nodes to approximate this, but the framework's path of least resistance
pushes toward blobs, because every extra node costs a new state channel and another
superstep — see (b).)*

**(b) State merging is implicit (reducers); here it is explicit (`goto` + `ctx.data`).**
In LangGraph a node returns a partial dict and the runtime merges it into shared state
via per-channel reducers you declared elsewhere. Two consequences for routing:
  - To pass a value between two steps you must add a *channel* to the typed state schema.
    Fine-grained decomposition therefore inflates the schema and the reducer config — the
    `Verdict` would have to become a persisted channel just to reach the router.
  - State can change behind the call site according to a reducer defined far away.

  Here, `goto()` constructs the next `State` explicitly and `Verdict` is a transient return
  value that never touches persisted state. If a value moved, one visible line moved it.
  For a control flow this retry-heavy, "no surprising merges" is worth more than automatic
  merging.

**(c) Loop control is a step counter; here it is semantic.** LangGraph's guard is
`recursion_limit` — a raw superstep count that raises `GraphRecursionError`. It will happily
run `repair → execute → fail → repair` 25 times on the *identical* error and then throw. The
signature loop-breaker (§6) detects "same error twice → escalate" — progress, not just
count — plus named per-failure-mode budgets and a model-tier escalation ladder. All three
are routing concerns LangGraph leaves to you to invent; once invented, the graph library is
mostly carrying state you've chosen to thread by hand anyway.

**(d) Cost vs. benefit for *this* scope.** The features LangGraph genuinely buys —
parallel superstep execution with automatic state merging, token streaming, checkpoint
time-travel — are exactly the features the **chat path does not need** (it's sequential,
turn-at-a-time, and persisted in SQLite already). The price would be a dependency, a
new execution model (Pregel supersteps, channels, reducers) to learn and debug, and the
erosion of the role separation in (a). A ~25-line engine with no dependency is more legible
and easier to reason about for a sequential, validation-heavy flow. The calculus flips the
day the **parallel report fan-out** is built — see §15.

## 14. Why not AutoGen (for routing)

AutoGen models a system as **conversing agents**: you create agents and let them exchange
messages, often with an LLM (or a group-chat manager) deciding who speaks next. That is the
opposite of what this routing needs.

**(a) AutoGen routes with a model; here routing is deterministic code.** In a group chat,
"who goes next" is itself frequently an LLM decision. This project's entire premise is that
**control flow must not be a model decision** — the next state is a pure function of a
typed `Verdict`. Putting an LLM in the router would reintroduce exactly the nondeterminism
and the hallucinated-control-flow the state machine exists to eliminate, and it would make
runs non-reproducible from the trace.

**(b) Conversation as the substrate fights minimal-context.** AutoGen agents accumulate a
shared message history. The design here is the reverse (§7 rule 2): each action sees the
profile + its one input, never the transcript, because long histories are where small
models start contradicting themselves. Modeling steps as chatting agents pulls toward
ever-growing context windows.

**(c) No structured verdict / validation ladder.** AutoGen has no first-class notion of
"validate this output at the cheapest level that catches its failure mode, classify the
error, and route on it." You'd rebuild the ladder, the `error_kind` classification, and the
signature loop-breaker on top of a conversational layer that is actively working against the
determinism you want.

**(d) Right tool, wrong problem.** AutoGen shines for open-ended, exploratory multi-agent
collaboration where the *path* is genuinely unknown. Here the path is known and small (§5):
classify → plan → write → execute → check → compose, with a fixed set of recovery branches.
For a known, bounded, must-be-reproducible flow, a transition table is simpler, cheaper, and
auditable; an agent conversation is more machinery for a problem that doesn't have its
shape.

---

## 15. The honest trade-offs

This architecture **out-opinions** both frameworks on the things they leave blank — strict
separation of concerns, a structured validation ladder, semantic loop-breaking, model-tier
escalation, full legibility, and a deterministic trace. It **pays for that** by hand-rolling
the things those frameworks build in:

- **No parallel fan-out yet.** The engine is a sequential loop. The `report`/`task` paths
  (where many tasks would run concurrently and merge) are not wired. The day that lands,
  the engine must grow concurrent execution + result merging — precisely what LangGraph's
  supersteps/reducers provide. Because `ctx.path` already abstracts "which flow," that can
  be added to *this* engine, or LangGraph adopted *only* for the fan-out path, without
  disturbing the chat path.
- **No token streaming.** `run_machine` returns a finished turn; the UI shows a pending
  bubble meanwhile.
- **No checkpoint time-travel.** There is solid SQLite persistence + rehydrate, but not
  free rewind/branch over a checkpointer.

For a single-threaded, validation-heavy analyst chat, that's a winning trade. It becomes a
genuine decision — keep hand-rolling vs. adopt a framework for one path — only when the
parallel report fan-out is built.
