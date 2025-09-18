"""Tests for :mod:`chainrunner`.

These tests intentionally avoid any live LLM dependencies.  When `chainrunner`
needs a LangChain model, the suite injects lightweight fakes into
``sys.modules`` so that the production code can import them without talking to
remote services.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest
from jsonschema.exceptions import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import chainrunner
from chainrunner import ConfigError


class DummyMessage:
    """Simple stand-in for LangChain messages."""

    def __init__(self, content: str) -> None:
        self.content = content


def make_python_command(snippet: str, *extra_args: str) -> list[str]:
    """Return a command list that executes ``snippet`` with ``sys.executable``."""

    return [sys.executable, "-c", snippet, *extra_args]


def install_fake_chatollama(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: Callable[[str], str],
    on_init: Callable[[dict[str, Any]], None] | None = None,
) -> type:
    """Register a fake ``langchain_ollama.ChatOllama`` implementation."""

    init_calls: dict[str, Any] = {}

    class FakeChatOllama:
        def __init__(self, model: str, base_url: str | None = None, **params: Any) -> None:
            init_calls.update({
                "model": model,
                "base_url": base_url,
                "params": params,
            })
            if on_init is not None:
                on_init(init_calls)

        def invoke(self, prompt: str) -> DummyMessage:
            return DummyMessage(response(prompt))

    fake_module = types.SimpleNamespace(ChatOllama=FakeChatOllama)
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake_module)
    return FakeChatOllama


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def test_render_template_substitutes_variables() -> None:
    result = chainrunner.render_template("Hello {{name}}", {"name": "World"})
    assert result == "Hello World"


def test_render_template_unknown_variable_raises_config_error() -> None:
    with pytest.raises(ConfigError, match="unknown variable: missing"):
        chainrunner.render_template("{{missing}}", {})


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def minimal_command_config() -> dict[str, Any]:
    return {
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"result": "string"},
                "command": make_python_command(
                    "import sys; print(sys.argv[1])", "{{userRequest}}"
                ),
            }
        ]
    }


def test_validate_config_accepts_valid_config() -> None:
    chainrunner.validate_config(minimal_command_config())


def test_validate_config_duplicate_step_number() -> None:
    cfg = minimal_command_config()
    duplicate = cfg["steps"][0].copy()
    cfg["steps"].append(duplicate)
    with pytest.raises(ConfigError, match="duplicate step number: 1"):
        chainrunner.validate_config(cfg)


def test_validate_config_unknown_input_reference() -> None:
    cfg = minimal_command_config()
    cfg["steps"][0]["inputs"] = ["unknown"]
    with pytest.raises(ConfigError, match="references unknown input 'unknown'"):
        chainrunner.validate_config(cfg)


def test_validate_config_llm_step_requires_model_or_ref() -> None:
    cfg = minimal_command_config()
    step = cfg["steps"][0]
    step.pop("command")
    step["systemPrompt"] = "Prompt"
    with pytest.raises(ConfigError, match="missing model or modelRef"):
        chainrunner.validate_config(cfg)


def test_validate_config_unknown_model_reference() -> None:
    cfg = minimal_command_config()
    step = cfg["steps"][0]
    step.pop("command")
    step["systemPrompt"] = "Prompt"
    step["modelRef"] = "missing"
    with pytest.raises(ConfigError, match="references unknown modelRef 'missing'"):
        chainrunner.validate_config(cfg)


def test_validate_config_accepts_inline_model_definition() -> None:
    cfg = {
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"reply": "string"},
                "systemPrompt": "{{userRequest}}",
                "model": {
                    "provider": "ollama",
                    "model": "stub",
                },
            }
        ]
    }

    chainrunner.validate_config(cfg)


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------


def test_model_registry_caches_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[str] = []

    def fake_build(self: chainrunner.ModelRegistry, info: chainrunner.ModelInfo):
        created.append(info.model)
        return object()

    monkeypatch.setattr(chainrunner.ModelRegistry, "_build", fake_build, raising=False)
    registry = chainrunner.ModelRegistry(
        [{"name": "foo", "provider": "ollama", "model": "bar"}]
    )
    first = registry.get("foo")
    second = registry.get("foo")
    assert first is second
    assert created == ["bar"]


def test_model_registry_unknown_model_ref() -> None:
    registry = chainrunner.ModelRegistry([])
    with pytest.raises(ConfigError, match="unknown modelRef: missing"):
        registry.get("missing")


def test_model_registry_from_inline_uses_build(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def fake_build(self: chainrunner.ModelRegistry, info: chainrunner.ModelInfo):
        received["provider"] = info.provider
        received["model"] = info.model
        received["base_url"] = info.base_url
        received["params"] = info.params
        return "inline-instance"

    monkeypatch.setattr(chainrunner.ModelRegistry, "_build", fake_build, raising=False)
    registry = chainrunner.ModelRegistry([])
    result = registry.from_inline(
        {
            "provider": "ollama",
            "model": "inline-model",
            "baseUrl": "http://ollama",
            "params": {"temperature": 0.0},
        }
    )
    assert result == "inline-instance"
    assert received == {
        "provider": "ollama",
        "model": "inline-model",
        "base_url": "http://ollama",
        "params": {"temperature": 0.0},
    }


def test_model_registry_build_instantiates_chatollama(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed: dict[str, object] = {}

    def capture_init(values: dict[str, Any]) -> None:
        constructed.update(values)

    FakeChatOllama = install_fake_chatollama(
        monkeypatch, response=lambda prompt: prompt, on_init=capture_init
    )

    registry = chainrunner.ModelRegistry(
        [
            {
                "name": "demo",
                "provider": "ollama",
                "model": "llm",
                "baseUrl": "http://local",
                "params": {"temperature": 0.1},
            }
        ]
    )
    instance = registry.get("demo")
    assert isinstance(instance, FakeChatOllama)
    assert constructed == {
        "model": "llm",
        "base_url": "http://local",
        "params": {"temperature": 0.1},
    }


def test_model_registry_rejects_unknown_provider() -> None:
    registry = chainrunner.ModelRegistry(
        [{"name": "bad", "provider": "not-ollama", "model": "foo"}]
    )
    with pytest.raises(ConfigError, match="unsupported provider: not-ollama"):
        registry.get("bad")


# ---------------------------------------------------------------------------
# Type coercion
# ---------------------------------------------------------------------------


def test_coerce_handles_string_and_numbers() -> None:
    assert chainrunner.coerce("value", "string") == "value"
    assert chainrunner.coerce("42", "number") == 42
    assert chainrunner.coerce("3.14", "number") == pytest.approx(3.14)


def test_coerce_invalid_number_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="cannot convert output to number"):
        chainrunner.coerce("not-a-number", "number")


def test_coerce_unknown_type_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="unsupported output type: boolean"):
        chainrunner.coerce("true", "boolean")


# ---------------------------------------------------------------------------
# Chain execution
# ---------------------------------------------------------------------------


def test_run_chain_with_command_steps() -> None:
    cfg = {
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"greeting": "string"},
                "command": make_python_command(
                    "import sys; print('Hello ' + sys.argv[1])", "{{userRequest}}"
                ),
            },
            {
                "step": 2,
                "inputs": ["greeting"],
                "outputs": {"length": "number"},
                "command": make_python_command(
                    "import sys; print(len(sys.argv[1]))", "{{greeting}}"
                ),
            },
        ]
    }
    result = chainrunner.run_chain(cfg, "World")
    assert result == 11


def test_run_chain_with_llm_step(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_chatollama(monkeypatch, response=str.upper)

    cfg = {
        "models": [
            {"name": "dummy", "provider": "ollama", "model": "stub", "params": {"temperature": 0}}
        ],
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"reply": "string"},
                "systemPrompt": "Echo: {{userRequest}}",
                "modelRef": "dummy",
            }
        ],
    }

    result = chainrunner.run_chain(cfg, "test")
    assert result == "ECHO: TEST"


def test_run_chain_requires_steps() -> None:
    cfg = {"steps": []}
    with pytest.raises(ValidationError, match="should be non-empty"):
        chainrunner.run_chain(cfg, "hi")


def test_run_chain_supports_inline_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_cfg: dict[str, Any] = {}

    def fake_from_inline(self: chainrunner.ModelRegistry, model_cfg: Mapping[str, Any]):
        captured_cfg.update(model_cfg)

        class InlineModel:
            def invoke(self, prompt: str) -> DummyMessage:
                return DummyMessage(f"inline:{prompt}")

        return InlineModel()

    monkeypatch.setattr(chainrunner.ModelRegistry, "from_inline", fake_from_inline, raising=False)

    cfg = {
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"reply": "string"},
                "systemPrompt": "Hi {{userRequest}}",
                "model": {
                    "provider": "ollama",
                    "model": "ephemeral",
                },
            }
        ]
    }

    result = chainrunner.run_chain(cfg, "there")
    assert result == "inline:Hi there"
    assert captured_cfg == {"provider": "ollama", "model": "ephemeral"}


def test_run_chain_surfaces_command_failure() -> None:
    cfg = {
        "steps": [
            {
                "step": 1,
                "inputs": ["userRequest"],
                "outputs": {"result": "string"},
                "command": make_python_command("import sys; sys.exit(1)"),
            }
        ]
    }

    with pytest.raises(subprocess.CalledProcessError):
        chainrunner.run_chain(cfg, "ignored")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = minimal_command_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    exit_code = chainrunner.main(["-c", str(config_path), "-i", "hello"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "hello"
    assert captured.err == ""


def test_main_config_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = minimal_command_config()
    cfg["steps"][0]["inputs"] = ["missing"]
    config_path = tmp_path / "bad.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    exit_code = chainrunner.main(["-c", str(config_path), "-i", "hello"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "CONFIG ERROR" in captured.err
    assert captured.out == ""


def test_main_runtime_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = minimal_command_config()
    cfg["steps"][0]["command"] = make_python_command("raise SystemExit('boom')")
    config_path = tmp_path / "boom.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    exit_code = chainrunner.main(["-c", str(config_path), "-i", "data"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR:" in captured.err
    assert captured.out == ""


# ---------------------------------------------------------------------------
# Config loading helpers
# ---------------------------------------------------------------------------


def test_load_config_supports_yaml(tmp_path: Path) -> None:
    cfg_text = """
steps:
  - step: 1
    inputs: [userRequest]
    outputs: {result: string}
    command:
      - python
      - -c
      - "import sys; print(sys.argv[1])"
      - "{{userRequest}}"
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(cfg_text, encoding="utf-8")
    cfg = chainrunner.load_config(cfg_path)
    assert cfg["steps"][0]["outputs"] == {"result": "string"}


def test_load_json_reads_json(tmp_path: Path) -> None:
    data = {"foo": "bar"}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert chainrunner.load_json(path) == data
