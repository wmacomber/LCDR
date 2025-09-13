# ARCHITECTURE.md

This document explains the internals of the config-driven runner.

---

## Core Concepts

- **Models:** Named presets for LLM providers (currently only Ollama).  
- **Steps:** Units of work, either `systemPrompt` (LLM) or `command` (process).  
- **Variables:** Flat namespace of values passed between steps.  
- **Runner:** The engine that executes steps in order and returns the final value.  
- **Validator:** A schema + semantic checker that ensures configs are safe and consistent before running.

---

## Execution Lifecycle

1. **Load config** (JSON or YAML).  
2. **Validate** against `config.schema.json` and semantic rules:
   - unique step numbers
   - valid `modelRef`s
   - inputs must come from prior steps or `userRequest`
3. **Initialize variables:** start with `{ "userRequest": <input text> }`.  
4. **Run steps in ascending order:**
   - Render inputs into templates.
   - Execute the step (LLM call or process).
   - Capture and coerce output → add/overwrite variable.  
5. **Return:** the sole output of the final step.

---

## Design Choices

- **Linear execution only.** Branching belongs inside tools or prompts.  
- **Flat namespace.** Later steps may overwrite prior outputs deliberately.  
- **Fail-fast validation.** Errors are surfaced before any execution.  
- **Schema-driven.** The config is governed by `config.schema.json` for consistency.  
- **Human-readable configs.** All tinkering happens in YAML/JSON, not Python.

---

## Extension Points

- **Providers:** Add new providers alongside `ollama` (e.g., OpenAI).  
- **Step types:** Beyond `systemPrompt` and `command`, future steps could include `httpRequest`, `regexReplace`, etc.  
- **Validators:** Add rules for richer type-checking or static analysis.

---

## Future Directions

- Multiple output keys per step.  
- Richer types (arrays, objects).  
- Branching or conditional execution.  
- Multi-message prompts for LLM steps.  
