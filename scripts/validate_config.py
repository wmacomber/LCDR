#!/usr/bin/env python3
"""
validate_config.py — MVP validator for the config-driven chain runner.

Usage:
  python validate_config.py path/to/config.(json|yaml|yml)

Looks for schema at ./config.schema.json (or change SCHEMA_PATH).
"""
from __future__ import annotations
import sys, json, pathlib
from typing import Any, Dict
try:
    import yaml  # pip install pyyaml
except Exception:
    yaml = None

try:
    from jsonschema import Draft7Validator
except Exception:
    print("ERROR: jsonschema is required: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

SCHEMA_PATH = pathlib.Path(__file__).parent.with_name("config.schema.json")

def load_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def load_config(path: pathlib.Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if yaml is None:
            raise
        return yaml.safe_load(text)

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python validate_config.py path/to/config.(json|yaml|yml)", file=sys.stderr)
        return 2

    cfg_path = pathlib.Path(sys.argv[1])
    if not cfg_path.exists():
        print(f"ERROR: file not found: {cfg_path}", file=sys.stderr)
        return 2

    try:
        cfg = load_config(cfg_path)
    except Exception as e:
        print(f"ERROR: failed to load config: {e}", file=sys.stderr)
        return 2

    try:
        schema = load_json(SCHEMA_PATH)
    except Exception as e:
        print(f"ERROR: failed to load schema {SCHEMA_PATH}: {e}", file=sys.stderr)
        return 2

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(cfg), key=lambda e: e.path)
    if errors:
        print("CONFIG VALIDATION ERRORS:", file=sys.stderr)
        for err in errors:
            path = "$" + "".join(f"[{repr(p)}]" if isinstance(p, int) else f".{p}" for p in err.path)
            print(f" - {path}: {err.message}", file=sys.stderr)
        return 1

    # semantic checks (modelRef, step uniqueness, dataflow) — same as before
    # ... copy that block over here ...

    print("OK: configuration is valid.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
