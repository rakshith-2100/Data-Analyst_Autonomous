# Prompts

Model **system prompts** live here as `.md` files — never inlined in `.py`. The **user
message** for each call is built in the action's Python code (`build_messages`), because
it's assembled from runtime data (the profile + the one input this action operates on).

```
prompts/
  actions/      # how an [agent] action PRODUCES its output
                #   classify, plan_step, write_code, repair, reduce, compose,
                #   ask, respond, plan_report, refine_report, narrate
  validators/   # how a MODEL-BASED validator JUDGES output (only these need prompts)
                #   sanity     — CHECK: "does the result answer the question?"
                #   grounding  — COMPOSE/NARRATE: "is every stated number traceable?"
```

Rules:
- **System prompt → `prompts/<area>/<name>.md`.** Edit prose here, not in code.
- **User prompt → built in code** (`build_messages(ctx)`), from `profile.as_prompt()` + the input.
- **Producing ≠ judging.** An action's prompt is separate from any validator prompt that
  later checks its output.
- Prompts are **grown stage by stage** — each new action stage adds its `.md` here.

Load with `from src.prompts import load_prompt` → `load_prompt("actions/classify")`.
