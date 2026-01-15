# LLM Council CLI

Terminal-first LLM council that runs multi-model debates and produces a
moderator synthesis.

## Setup

1) Create a virtual environment (Python 3.10+) and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Create a config file (run from the repo root):

```bash
python -m llm_council init-config
```

This writes `~/.config/llm_council/config.toml`. Edit it with your model IDs and
API key settings. Keys can be stored in the config or provided via environment
variables.

## Usage

```bash
python -m llm_council ask "Design a migration plan for a monolith to services."
python -m llm_council repl
python -m llm_council models
```

History is stored at `~/.config/llm_council/history.jsonl` by default.

## Notes

- Set `providers.anthropic.thinking` and `providers.openai.reasoning` in the
  config to enable extended thinking features where supported.

## Getting started (new terminal session)

From a fresh terminal, run everything from the repo root:

```bash
cd /Users/zhl/Documents/02_Area_Code/llm_council_cli_codex
source .venv/bin/activate
```

Then run a debate:

```bash
python -m llm_council ask "Your question here"
```

If you prefer not to activate the venv, you can run:

```bash
./.venv/bin/python -m llm_council ask "Your question here"
```
