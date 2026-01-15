from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List

from .config import CONFIG_TEMPLATE, DEFAULT_CONFIG_PATH, expand_path, load_config, resolve_api_key
from .debate import DebateResult, run_debate
from .history import append_history
from .providers import get_provider
from .providers.base import ProviderError


def ensure_repo_cwd() -> None:
    cwd = Path.cwd()
    marker_pyproject = cwd / "pyproject.toml"
    marker_pkg = cwd / "llm_council"
    if not marker_pyproject.is_file() or not marker_pkg.is_dir():
        print(
            "Error: Run this CLI from the repo root (folder containing "
            "pyproject.toml and llm_council/).",
            file=sys.stderr,
        )
        sys.exit(2)


def main() -> None:
    ensure_repo_cwd()
    parser = argparse.ArgumentParser(prog="llm-council", description="LLM Council CLI")
    subparsers = parser.add_subparsers(dest="command")

    ask_parser = subparsers.add_parser("ask", help="Run a council debate for a prompt")
    ask_parser.add_argument("prompt", help="Prompt to send to the council")
    ask_parser.add_argument("--config", help="Path to config file")
    ask_parser.add_argument("--no-history", action="store_true", help="Disable history logging")
    ask_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for results",
    )

    repl_parser = subparsers.add_parser("repl", help="Interactive council REPL")
    repl_parser.add_argument("--config", help="Path to config file")
    repl_parser.add_argument("--no-history", action="store_true", help="Disable history logging")
    repl_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for results",
    )

    models_parser = subparsers.add_parser("models", help="List provider models")
    models_parser.add_argument("--config", help="Path to config file")
    models_parser.add_argument(
        "--provider", choices=["gemini", "anthropic", "openai", "all"], default="all"
    )

    init_parser = subparsers.add_parser("init-config", help="Create a starter config file")
    init_parser.add_argument("--path", help="Path for the config file")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")

    args = parser.parse_args()

    if args.command == "ask":
        cfg = load_config(args.config)
        try:
            result = run_debate(args.prompt, cfg)
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            sys.exit(1)
        print_output(result, output_format=args.format)
        if not args.no_history:
            write_history(result, cfg)
        return

    if args.command == "repl":
        cfg = load_config(args.config)
        run_repl(cfg, no_history=args.no_history, output_format=args.format)
        return

    if args.command == "models":
        cfg = load_config(args.config)
        list_models(cfg, args.provider)
        return

    if args.command == "init-config":
        config_path = Path(args.path) if args.path else DEFAULT_CONFIG_PATH
        write_config(config_path, args.force)
        return

    parser.print_help()


def run_repl(cfg: Dict[str, Any], no_history: bool, output_format: str) -> None:
    print("LLM Council REPL. Type 'exit' or Ctrl-D to quit.")
    while True:
        try:
            prompt = input("council> ").strip()
        except EOFError:
            print()
            break
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", ":q"}:
            break
        try:
            result = run_debate(prompt, cfg)
        except ValueError as exc:
            print(f"Configuration error: {exc}")
            continue
        print_output(result, output_format=output_format)
        if not no_history:
            write_history(result, cfg)


def list_models(cfg: Dict[str, Any], provider_name: str) -> None:
    providers = cfg.get("providers", {})
    provider_names = [provider_name] if provider_name != "all" else list(providers.keys())
    timeout_s = cfg.get("request", {}).get("timeout_s", 60)
    for name in provider_names:
        provider_cfg = providers.get(name, {})
        api_key = resolve_api_key(provider_cfg)
        if not api_key:
            print(f"{name}: missing API key")
            continue
        provider = get_provider(name)
        base_url = provider_cfg.get("base_url", "")
        try:
            models = provider.list_models(api_key, base_url, timeout_s)
        except ProviderError as exc:
            print(f"{name}: error listing models: {exc}")
            continue
        print(f"{name}:")
        for model_id in models:
            print(f"  - {model_id}")


def write_config(path: Path, force: bool) -> None:
    path = path.expanduser()
    if path.exists() and not force:
        print(f"Config already exists at {path}. Use --force to overwrite.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    print(f"Wrote config to {path}")


def write_history(result: DebateResult, cfg: Dict[str, Any]) -> None:
    history_path = cfg.get("history", {}).get("path", "~/.config/llm_council/history.jsonl")
    history_path = expand_path(history_path)
    append_history(serialize_result(result), history_path)


def print_output(result: DebateResult, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(serialize_result(result), ensure_ascii=True, indent=2))
        return
    print_debate(result)


def serialize_result(result: DebateResult) -> Dict[str, Any]:
    return {
        "prompt": result.prompt,
        "members": [
            {"provider": reply.member.provider, "model": reply.member.model}
            for reply in result.round1
        ],
        "round1": [
            {
                "member": reply.member.label(),
                "text": reply.text,
                "error": reply.error,
            }
            for reply in result.round1
        ],
        "round2": [
            {
                "member": reply.member.label(),
                "text": reply.text,
                "error": reply.error,
            }
            for reply in result.round2
        ],
        "moderator": {
            "member": result.moderator.member.label() if result.moderator else "",
            "text": result.moderator.text if result.moderator else "",
            "error": result.moderator.error if result.moderator else "missing moderator",
        },
    }


def print_debate(result: DebateResult) -> None:
    print_section("Round 1", result.round1)
    print_section("Round 2 (Rebuttals)", result.round2)
    print_section("Moderator", [result.moderator] if result.moderator else [])


def print_section(title: str, replies: List[Any]) -> None:
    divider = "=" * max(10, len(title) + 6)
    print(divider)
    print(f"== {title} ==")
    print(divider)
    if not replies:
        print("(no responses)")
        print("")
        return
    for reply in replies:
        print_reply(reply)
        print("")


def print_reply(reply: Any) -> None:
    label = reply.member.label()
    if reply.error:
        print(f"[{label}] ERROR: {reply.error}")
        return
    text = reply.text.strip() if reply.text else "(no response)"
    indented = textwrap.indent(text, "  ")
    print(f"[{label}]")
    print(indented)


if __name__ == "__main__":
    main()
