# AGENTS.md

This project is designed around the idea of **agents**: configurable chains of steps that transform an input text into an output text.  
Agents are not hardcoded; they are **defined entirely by JSON or YAML configs**.

---

## What Is an Agent?

An *agent* in this repo is a sequence of **steps**:
- Each step consumes variables, either from the initial input (`userRequest`) or from prior steps’ outputs.
- Each step produces exactly one output variable.
- Steps may be **LLM-backed** (using models like Ollama) or **command-backed** (running local processes).

Execution is linear and deterministic: step 1 → step 2 → … → step N.  
There is no branching or conditional logic in this MVP; complexity belongs *inside* steps, not between them.

---

## Anatomy of a Step

Example LLM step:

```json
{
  "step": 1,
  "inputs": ["userRequest"],
  "outputs": { "sentiment": "string" },
  "modelRef": "sentiment-llama",
  "systemPrompt": "You are a sentiment analyzer. Answer only with [positive,neutral,negative].\\n\\n{{userRequest}}"
}
````

Example command step:

```json
{
  "step": 2,
  "inputs": ["userRequest"],
  "outputs": { "wordCount": "number" },
  "command": ["python", "wordcounter.py", "{{userRequest}}"]
}
```

---

## Variable Rules

* Reserved variable: `userRequest` = the initial input to the agent.
* Steps produce variables into a **flat global namespace**.
* Variables may be overwritten by later steps; the **latest value wins**.
* Templates use `{{var}}` substitution only — no logic, no formatting.

---

## Defining Models

Models are declared at the top level:

```json
{
  "name": "sentiment-llama",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "baseUrl": "http://localhost:11434",
  "params": { "temperature": 0.0 }
}
```

Steps reference them via `modelRef`.

---

## Example Agent Config

```json
{
  "models": [
    {
      "name": "default-llama",
      "provider": "ollama",
      "model": "llama3.1:8b",
      "baseUrl": "http://localhost:11434"
    }
  ],
  "steps": [
    {
      "step": 1,
      "inputs": ["userRequest"],
      "outputs": { "gist": "string" },
      "modelRef": "default-llama",
      "systemPrompt": "Summarize this request in one short sentence:\\n\\n{{userRequest}}"
    }
  ]
}
```

---

## Related Docs

* See [ARCHITECTURE.md](ARCHITECTURE.md) for execution details.
* See [CONTRIBUTING.md](CONTRIBUTING.md) for how to extend step types.
* See [SECURITY.md](SECURITY.md) for safe usage practices.
