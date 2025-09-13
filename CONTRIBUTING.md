# CONTRIBUTING.md

Thank you for your interest in improving this project!  
Our goal is to keep configs human-friendly and the codebase stable.

---

## Development Setup

```bash
git clone <repo>
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
````

Dependencies:

* `jsonschema` for validation
* `pyyaml` for YAML parsing
* `pytest` for testing

---

## Workflow

1. Fork and branch (`feature/my-change`).
2. Make changes with clear commits.
3. Run tests and validation locally.
4. Submit a pull request.

---

## Code Guidelines

* Follow PEP8 + type hints (`from __future__ import annotations`).
* Prefer small, composable functions.
* Write docstrings for all public functions.
* Keep logic minimal in CLI entrypoints.

---

## Adding Features

* Update `config.schema.json` to reflect new fields.
* Extend the runner to implement behavior.
* Add validator checks if semantics require it.
* Document the feature in [AGENTS.md](AGENTS.md).
* Add unit tests in `tests/`.

---

## Testing

Run all tests with:

```bash
pytest
```

Validate configs with:

```bash
python validate_config.py examples/agent.json
```

---

## Philosophy

Keep user configs **clear and simple**.
Don’t add complexity unless it clearly benefits tinkering at the config level.
