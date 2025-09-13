# SECURITY.md

This project executes instructions from external config files.  
That power comes with responsibility.

---

## Threat Model

- **Command steps** run arbitrary processes. Treat them as code execution.  
- **LLM steps** may send sensitive data to external providers.  
- **Configs** may be malicious if obtained from untrusted sources.

---

## Safe Usage Guidelines

- Only run configs you wrote or trust.  
- Avoid running `command` steps from unverified sources.  
- Keep providers local (e.g., Ollama) for sensitive data.  
- If using remote APIs, review their privacy and data-retention policies.  
- Run in isolated environments (Docker, venv) when possible.

---

## Dependencies

- Keep `jsonschema`, `pyyaml`, and other dependencies updated.  
- Use `pip-audit` or similar tools to scan for vulnerabilities.  

---

## Reporting Vulnerabilities

If you discover a security issue:
1. Do not open a public GitHub issue.  
2. Instead, email the maintainers at **[admin@macomber.tech]** or use the repository’s Security tab (if enabled).  

---

## Roadmap

Future work may include:
- Sandboxing for command steps (e.g. someday it may be cool to consume a docker container as a step).
- Static analyzers for risky templates.
