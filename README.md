# Config-Driven Chain Runner

A lightweight Python 3.11 tool for building and running **configurable LangChain pipelines**.  
Define your pipeline once in JSON or YAML — no code changes required.

---

## ✨ Features

- **Config-driven:** Define steps, models, and inputs in plain JSON/YAML.  
- **Linear pipelines:** Steps run in order (1 → N). No branching, no hidden logic.  
- **Mixed step types:**
  - **LLM-backed steps** using [LangChain](https://python.langchain.com/) and Ollama.
  - **Command-backed steps** running local processes.  
- **Flat variable namespace:** Each step produces exactly one variable. Later steps may overwrite earlier outputs (latest value wins).  
- **Strict validation:** Configs are checked against `config.schema.json` + semantic rules before execution.  
- **Safe defaults:** Fail-fast error handling, explicit typing (`string` or `number`).  

---

## 📦 Requirements

- Python **3.11** (pinned project version).  
- Dependencies listed in [requirements.txt](requirements.txt).  
- Ollama daemon running locally (default `http://localhost:11434`) for LLM steps.

---

## 🚀 Quickstart

1. **Install dependencies**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
````

2. **Create a config file** (e.g. `examples/sentiment.json`)

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
      "outputs": { "sentiment": "string" },
      "modelRef": "default-llama",
      "systemPrompt": "You are a sentiment analyzer. Respond with [positive,neutral,negative].\\n\\n{{userRequest}}"
    }
  ]
}
```

3. **Run the chain**

```bash
python src/chainrunner.py -c examples/sentiment.json -i "I absolutely love this project!"
```

Output:

```
positive
```

---

## 🛠️ Validation

Always validate configs before running:

```bash
python scripts/validate_config.py examples/sentiment.json
```

You’ll see either:

```
OK: configuration is valid.
```

or detailed errors explaining what’s wrong (bad refs, missing inputs, invalid types, etc.).

---

## 🧪 Testing

The automated test suite lives under `tests/` and can be executed entirely
offline.  Install the development dependencies and run `pytest`:

```bash
pip install -r requirements-dev.txt
pytest
```

The tests provide lightweight stubs for `langchain_ollama.ChatOllama`, so no
Ollama daemon or other LLM provider is required.

---

## 📂 Repository Layout

```
.
├── AGENTS.md                   # How agents are defined and used
├── ARCHITECTURE.md             # Internal design and flow
├── CONTRIBUTING.md             # How to extend and contribute
├── SECURITY.md                 # Safe usage guidelines
├── src/chainrunner.py          # Main entrypoint
├── scripts/validate_config.py  # Config validator
├── config.schema.json          # JSON Schema definition
├── requirements.txt            # Dependencies
├── requirements-dev.txt        # Dev dependencies
└── examples/                   # Example configs and tools
```

---

## 🔒 Security Notes

* **Command steps execute arbitrary code**. Never run untrusted configs.
* Treat LLM steps as potentially sensitive (data may be sent to providers).
* See [SECURITY.md](SECURITY.md) for full details.

---

## 🤝 Contributing

Contributions are welcome!
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for setup and guidelines.

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
