from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib as toml
except ImportError:  # pragma: no cover
    import tomli as toml


DEFAULT_CONFIG_PATH = Path(
    os.environ.get("LLM_COUNCIL_CONFIG", "~/.config/llm_council/config.toml")
).expanduser()

DEFAULTS: Dict[str, Any] = {
    "council": {"members": ["gemini", "anthropic", "openai"]},
    "moderator": {"provider": "openai", "model": ""},
    "history": {"path": "~/.config/llm_council/history.jsonl"},
    "request": {"timeout_s": 60, "temperature": 0.2, "max_output_tokens": 1024},
    "providers": {
        "gemini": {
            "api_key_env": "GEMINI_API_KEY",
            "model": "",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        },
        "anthropic": {
            "api_key_env": "ANTHROPIC_API_KEY",
            "model": "",
            "base_url": "https://api.anthropic.com/v1",
            "version": "2023-06-01",
        },
        "openai": {
            "api_key_env": "OPENAI_API_KEY",
            "model": "",
            "base_url": "https://api.openai.com/v1",
        },
    },
}

CONFIG_TEMPLATE = """\
[council]
members = ["gemini", "anthropic", "openai"]

[moderator]
provider = "openai"
model = "gpt-4.1-mini"

[history]
path = "~/.config/llm_council/history.jsonl"

[request]
timeout_s = 60
temperature = 0.2
max_output_tokens = 1024

[providers.gemini]
api_key_env = "GEMINI_API_KEY"
model = "gemini-1.5-pro"
base_url = "https://generativelanguage.googleapis.com/v1beta"

[providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"
model = "claude-3-5-sonnet-20240620"
base_url = "https://api.anthropic.com/v1"
version = "2023-06-01"
thinking = { type = "enabled", budget_tokens = 1024 }

[providers.openai]
api_key_env = "OPENAI_API_KEY"
model = "gpt-4.1-mini"
base_url = "https://api.openai.com/v1"
reasoning = { effort = "medium" }
"""


def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path = config_path.expanduser()
    data: Dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = toml.load(handle)
    return merge_dicts(DEFAULTS, data)


def merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_api_key(provider_cfg: Dict[str, Any]) -> str | None:
    if provider_cfg.get("api_key"):
        return str(provider_cfg["api_key"]).strip()
    env_name = provider_cfg.get("api_key_env")
    if env_name:
        return os.environ.get(env_name)
    return None


def expand_path(path_value: str) -> str:
    return str(Path(path_value).expanduser())
