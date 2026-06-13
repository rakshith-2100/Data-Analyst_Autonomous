# Data Analyst Agent

Upload a CSV and **chat with your data** — ask anything in plain English and get back a
real answer plus charts and tables, computed by actual `pandas`/`matplotlib` code (never
guessed by the model). A planned **report** mode lets you pick the charts and stats you
want and get a written analysis.

The whole system is built from **three primitives** — one model, one tool (run Python in a
sandbox), one result shape — arranged as a **validated state machine**. The model never
does "the analysis"; it only ever performs one tiny, bounded task (classify a message, plan
one step, write one code cell, write two sentences), and a deterministic harness routes,
validates, retries, and escalates around those calls. Numbers come from code; the model
only writes the prose on top — which is what kills hallucinated figures.

> **What's different about it:** routing is a hand-written, deterministic state machine —
> not LangGraph, not AutoGen. The full reasoning is in
> **[docs/architecture.md](docs/architecture.md)**.

---

## Run guidelines

**Prerequisites:** Python 3.11+, Node 18+, and an OpenAI API key.

### One command (recommended)

```powershell
# Windows / PowerShell
powershell -ExecutionPolicy Bypass -File run.ps1
```

```bash
# Linux / macOS
chmod +x run.sh && ./run.sh
```

The script creates a `.venv`, installs backend (`data_analyst/requirements.txt`) and
frontend (`app/`) dependencies, copies `data_analyst/.env.example` → `data_analyst/.env`
on first run, then starts both servers:

- backend → <http://127.0.0.1:8000> (interactive docs at `/docs`)
- frontend → <http://localhost:5173>

> **First run:** edit `data_analyst/.env` and set `OPENAI_API_KEY` before chatting.
> Optionally set `OPENAI_MODEL_CHEAP` (default `gpt-4.1-mini`) and `OPENAI_MODEL_STRONG`
> (default `gpt-4.1`).

### Manual

```bash
# backend  (from data_analyst/)
python -m venv .venv && . .venv/Scripts/activate   # or  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env -> OPENAI_API_KEY
uvicorn src.api:app --reload

# frontend (from app/)
npm install
npm run dev
```

Then open <http://localhost:5173>, upload a CSV (or click the bundled **Telco churn**
sample), and start asking questions.

### Quick smoke tests

Several modules run standalone — handy for verifying a layer in isolation:

```bash
cd data_analyst
python -m src.sandbox        # exercise code execution + error classification
python -m src.orchestrator   # run the engine on a fake 2-step machine
python -m src.chat           # a full multi-turn chat against the sample data
python -m src.api            # spin the API through a scripted session (incl. restart)
```

---

## Architecture at a glance

A React/TypeScript SPA talks to a FastAPI backend whose core is a **generic, domain-blind
state-machine engine**. Each turn is the same loop:

```
state → action (do the work) → validate (judge it) → transition (decide next) → trace
```

Four roles, four places, never blurred:

| Role | Lives in | Does | Routes? |
|---|---|---|---|
| **Action** | `actions/` | does the work — a model call `[agent]` or plain code `[sys]` | never |
| **Validator** | `validators/` | judges the output → returns a `Verdict` | never |
| **Transition** | `transitions/` | reads the `Verdict`, returns the next state | **only this** |
| **Orchestrator** | `orchestrator.py` | turns the crank; knows no domain | never |

The engine itself is ~25 lines (`data_analyst/src/orchestrator.py`) and knows no state
name except the terminal set `{DONE, FAIL, AWAIT}`. The chat path runs:

```
CLASSIFY → PLAN_STEP → WRITE_CODE → EXECUTE → CHECK → COMPOSE → DELIVER → DONE
```

with error branches into `ENRICH → REPAIR`, `REDUCE`, and a two-rung `ESCALATE` ladder
(re-strategize → stronger model → fail honestly). Reliability comes from three control
mechanisms living at the right layers — **named per-failure retry counters**, a
**signature loop-breaker** ("same error twice → escalate, don't repeat"), and a
**validation ladder** where four of six checks cost zero model calls. Model-written code
runs in a **sandboxed subprocess** with a wall-clock timeout. Sessions, messages, and
chart artifacts persist in SQLite and rehydrate after a restart.

```
data_analyst/src/
  orchestrator.py   core.py        # the engine + the dataclasses it threads (State, Verdict, ...)
  actions/  validators/  transitions/   # do the work · judge it · route
  models.py  sandbox.py             # the one OpenAI client · subprocess code execution
  chat.py  api.py  db.py            # session memory + AWAIT-resume · FastAPI · SQLite
app/                                # React 19 + TypeScript + Vite frontend
```

**Why a hand-written state machine and not LangGraph or AutoGen?** Short version:
LangGraph doesn't *enforce* the action/validator/transition split and merges state
implicitly via reducers; AutoGen routes with a model, which reintroduces exactly the
nondeterminism this design removes. Both are good tools for a different shape of problem.
The long, low-level version — with code — is in
**[docs/architecture.md](docs/architecture.md)** (§13–§14). Deeper design docs live in
[docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md) and
[docs/TRANSITION_TABLE.md](docs/TRANSITION_TABLE.md).

---

## Next improvements

- **Wire the report path.** `PLAN_REPORT → DISPATCH → NARRATE → ASSEMBLE` reusing the chat
  actions. `DISPATCH` fans out, running `WRITE_CODE → EXECUTE → ENRICH → REPAIR → CHECK`
  per task in isolation; `REFINE_REPORT` emits an `{add, drop, keep}` diff so a refine is
  an edit, not a rebuild. The `report`/`task` transition tables and actions are currently
  stubs.
- **Parallel fan-out + result merge.** The engine is sequential today. The report path
  needs concurrent task execution and merging — the one place where adopting (or borrowing
  from) LangGraph's supersteps/reducers becomes a real option, scoped to *that* path only.
- **Token streaming.** Stream the answer (and intermediate progress) to the UI instead of
  returning a finished turn after a pending bubble.
- **Persistent chat namespace.** Keep one sandbox across chat turns so follow-ups like
  "now show it as a pie" build on prior state; report tasks stay stateless.
- **Harden the sandbox.** Swap the subprocess for a Docker/e2b executor (the interface
  already allows it) to move past the "buggy, not malicious" threat model.
- **Eval harness.** Seed `eval/cases.yaml` (start with the `TotalCharges` dirty-data case)
  and run on every change, replaying from the per-session trace.

---

## Dataset

The bundled sample is **Telco Customer Churn** (7,043 rows × 21 columns). It has a built-in
gotcha — `TotalCharges` looks numeric but contains blank strings, so a naive `.mean()`
raises — which makes it the perfect exercise for the `EXECUTE → ENRICH → REPAIR` path.
Known truths to sanity-check answers against: month-to-month contracts churn far more than
longer ones; higher monthly charges correlate with churn.
