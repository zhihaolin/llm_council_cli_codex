# LLM Council CLI

A terminal-based tool that runs structured debates between multiple LLMs (GPT, Claude, Gemini) and synthesizes their responses into a single, balanced answer. Useful for getting diverse perspectives on complex questions where a single model might have blind spots.

## How It Works

1. **Round 1**: Each council member independently answers your question
2. **Round 2**: Each member sees others' responses and provides rebuttals/improvements
3. **Moderator**: A designated model synthesizes all responses into a final recommendation

## Features

- Multi-provider support: OpenAI, Anthropic, and Google Gemini
- Two-round debate format with rebuttals
- Moderator synthesis for balanced conclusions
- Interactive REPL mode for iterative questioning
- JSON output for programmatic use
- Configurable models, temperature, and token limits
- Session history logging

## Quick Start

```bash
# Clone and setup
git clone https://github.com/zhihaolin/llm_council_cli_codex.git
cd llm_council_cli_codex
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate config file
python -m llm_council init-config

# Edit ~/.config/llm_council/config.toml with your API keys, then run:
python -m llm_council ask "What's the best approach for migrating a monolith to microservices?"
```

## Usage

```bash
# One-off question
python -m llm_council ask "Your question here"

# Interactive mode
python -m llm_council repl

# List available models from configured providers
python -m llm_council models

# JSON output (for scripting)
python -m llm_council ask "Your question" --format json

# Disable colors
python -m llm_council ask "Your question" --color never
```

## Configuration

The config file lives at `~/.config/llm_council/config.toml`. You can set API keys directly or reference environment variables:

```toml
[council]
members = ["gemini", "anthropic", "openai"]

[moderator]
provider = "openai"
model = "gpt-4o"

[providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"  # or use api_key = "sk-..."
model = "claude-sonnet-4-5-20250929"
```

Extended thinking features can be enabled for supported models:

```toml
[providers.anthropic]
thinking = { type = "enabled", budget_tokens = 1024 }

[providers.openai]
reasoning = { effort = "medium" }
```

## Requirements

- Python 3.10+
- API keys for at least one provider (OpenAI, Anthropic, or Gemini)

## Acknowledgments

Inspired by [llm-council](https://github.com/karpathy/llm-council) by Andrej Karpathy.
