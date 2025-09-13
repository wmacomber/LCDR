#!/usr/bin/env python3
"""chainrunner.py

Execute a config-defined sequence of steps.

This file implements the minimal functionality described in README/ARCHITECTURE.
It loads a JSON/YAML configuration, validates it against ``config.schema.json``
plus a few semantic rules, then executes each step in order.  Steps may be
LLM-backed (currently only ``ollama`` via ``langchain_ollama``) or local command
steps executed with ``subprocess``.

Example:
    python src/chainrunner.py -c examples/sentiment.json -i "hello"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, MutableMapping

try:
    import yaml
except Exception:  # pragma: no cover - optional dep
    yaml = None  # type: ignore

try:
    from jsonschema import Draft7Validator
except Exception as exc:  # pragma: no cover - jsonschema is required
    raise SystemExit("jsonschema is required: pip install jsonschema") from exc

# In case you want to verify that the chain is running in the right order
# import langchain
# langchain.debug = True

# ---- Config loading -------------------------------------------------------

SCHEMA_PATH = pathlib.Path(__file__).parent.with_name("config.schema.json")
TEMPLATE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class ConfigError(RuntimeError):
    """Raised when the configuration fails validation."""


@dataclass
class ModelInfo:
    provider: str
    model: str
    base_url: str | None = None
    params: Dict[str, Any] | None = None


class ModelRegistry:
    """Instantiate and cache models declared in the config."""

    def __init__(self, models: Iterable[Mapping[str, Any]] | None = None) -> None:
        self._defs: Dict[str, ModelInfo] = {}
        self._cache: Dict[str, Any] = {}
        if models:
            for m in models:
                self._defs[m["name"]] = ModelInfo(
                    provider=m["provider"],
                    model=m["model"],
                    base_url=m.get("baseUrl"),
                    params=m.get("params"),
                )

    # Internal helper ------------------------------------------------------
    def _build(self, info: ModelInfo) -> Any:
        if info.provider != "ollama":
            raise ConfigError(f"unsupported provider: {info.provider}")
        from langchain_ollama import ChatOllama

        params = info.params or {}
        return ChatOllama(model=info.model, base_url=info.base_url, **params)

    # Public API -----------------------------------------------------------
    def get(self, name: str) -> Any:
        if name not in self._cache:
            info = self._defs.get(name)
            if info is None:
                raise ConfigError(f"unknown modelRef: {name}")
            self._cache[name] = self._build(info)
        return self._cache[name]

    def from_inline(self, model_cfg: Mapping[str, Any]) -> Any:
        info = ModelInfo(
            provider=model_cfg["provider"],
            model=model_cfg["model"],
            base_url=model_cfg.get("baseUrl"),
            params=model_cfg.get("params"),
        )
        return self._build(info)


# ---- Utility --------------------------------------------------------------


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


def render_template(template: str, variables: Mapping[str, Any]) -> str:
    """Replace ``{{var}}`` placeholders using ``variables``."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise ConfigError(f"unknown variable: {key}")
        return str(variables[key])

    return TEMPLATE_RE.sub(repl, template)


# ---- Validation -----------------------------------------------------------


def validate_config(cfg: Mapping[str, Any]) -> None:
    """Validate ``cfg`` structurally and semantically."""

    schema = load_json(SCHEMA_PATH)
    Draft7Validator(schema).validate(cfg)

    models = {m["name"] for m in cfg.get("models", [])}
    seen_steps: set[int] = set()
    known_vars: set[str] = {"userRequest"}

    for step in sorted(cfg["steps"], key=lambda s: s["step"]):
        step_no = step["step"]
        if step_no in seen_steps:
            raise ConfigError(f"duplicate step number: {step_no}")
        seen_steps.add(step_no)

        for inp in step["inputs"]:
            if inp not in known_vars:
                raise ConfigError(f"step {step_no} references unknown input '{inp}'")

        if "systemPrompt" in step:
            if "modelRef" in step:
                if step["modelRef"] not in models:
                    raise ConfigError(
                        f"step {step_no} references unknown modelRef '{step['modelRef']}'"
                    )
            elif "model" not in step:
                raise ConfigError(
                    f"step {step_no} missing model or modelRef for LLM step"
                )

        out_name = next(iter(step["outputs"].keys()))
        known_vars.add(out_name)


# ---- Execution ------------------------------------------------------------


def coerce(value: str, expected_type: str) -> Any:
    if expected_type == "string":
        return value
    if expected_type == "number":
        try:
            num = float(value)
        except ValueError as exc:
            raise RuntimeError(f"cannot convert output to number: {value!r}") from exc
        if num.is_integer():
            return int(num)
        return num
    raise RuntimeError(f"unsupported output type: {expected_type}")


def run_chain(cfg: Mapping[str, Any], user_input: str) -> Any:
    validate_config(cfg)
    registry = ModelRegistry(cfg.get("models"))
    variables: Dict[str, Any] = {"userRequest": user_input}

    steps = sorted(cfg["steps"], key=lambda s: s["step"])
    final_var = None
    for step in steps:
        out_name, out_type = next(iter(step["outputs"].items()))
        final_var = out_name

        # Render inputs into templates
        if "systemPrompt" in step:
            prompt = render_template(step["systemPrompt"], variables)
            if "modelRef" in step:
                llm = registry.get(step["modelRef"])
            else:
                llm = registry.from_inline(step["model"])
            # run model
            result = llm.invoke(prompt)  # returns a BaseMessage
            output_text = getattr(result, "content", str(result)).strip()
        else:  # command step
            cmd = [render_template(x, variables) for x in step["command"]]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            output_text = proc.stdout.strip()

        variables[out_name] = coerce(output_text, out_type)

    if final_var is None:
        raise RuntimeError("no steps to execute")
    return variables[final_var]


# ---- CLI ------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a config-defined chain")
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        type=pathlib.Path,
        help="Path to config JSON or YAML",
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Initial user request string"
    )
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        result = run_chain(cfg, args.input)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover - runtime errors
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
