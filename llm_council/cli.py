from __future__ import annotations

import argparse
import json
import re
import shutil
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
    ask_parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="always",
        help="Colorize text output",
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
    repl_parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="always",
        help="Colorize text output",
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
        print_output(result, output_format=args.format, color_mode=args.color)
        if not args.no_history:
            write_history(result, cfg)
        return

    if args.command == "repl":
        cfg = load_config(args.config)
        run_repl(cfg, no_history=args.no_history, output_format=args.format, color_mode=args.color)
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


def run_repl(cfg: Dict[str, Any], no_history: bool, output_format: str, color_mode: str) -> None:
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
        print_output(result, output_format=output_format, color_mode=color_mode)
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


def print_output(result: DebateResult, output_format: str, color_mode: str) -> None:
    if output_format == "json":
        print(json.dumps(serialize_result(result), ensure_ascii=True, indent=2))
        return
    styler = Styler.from_mode(color_mode)
    print_debate(result, styler)


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


def print_debate(result: DebateResult, styler: "Styler") -> None:
    width = get_terminal_width()
    print_section("Round 1", result.round1, styler, width)
    print_section("Round 2 (Rebuttals)", result.round2, styler, width)
    print_section("Moderator", [result.moderator] if result.moderator else [], styler, width)


def print_section(title: str, replies: List[Any], styler: "Styler", width: int) -> None:
    phase_color = phase_border_color(title)
    note = phase_note(title)
    render_box(
        [styler.italic(note)],
        width,
        styler,
        border_color=phase_color,
        title=title,
        title_align="center",
        title_color=phase_color,
    )
    print("")
    if not replies:
        empty_line = pad_text(styler.italic("(no responses)"), width - 4)
        render_box([empty_line], width, styler, border_color=phase_color)
        print("")
        return
    for reply in replies:
        print_reply_box(reply, styler, width)
        print("")


def print_reply_box(reply: Any, styler: "Styler", width: int) -> None:
    label = reply.member.label()
    provider_color = provider_border_color(reply.member.provider)
    content_width = width - 4
    lines: List[str] = []
    if reply.error:
        error_lines = wrap_lines(f"ERROR: {reply.error}", content_width - 2)
        for line in error_lines:
            styled = styler.bold(styler.red(line))
            lines.append(pad_text("  " + styled, content_width))
    else:
        body = reply.text.strip() if reply.text else "(no response)"
        body_lines = wrap_lines(body, content_width - 2)
        for line in body_lines:
            lines.append(pad_text("  " + line, content_width))
    render_box(
        lines,
        width,
        styler,
        border_color=provider_color,
        title=label,
        title_align="left",
        title_color=provider_color,
    )


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_PATTERN.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_ansi(text))


def pad_text(text: str, width: int) -> str:
    padding = width - visible_len(text)
    if padding <= 0:
        return text
    return text + (" " * padding)


def wrap_lines(text: str, width: int) -> List[str]:
    if width <= 0:
        return [text]
    lines: List[str] = []
    for raw in text.splitlines():
        if raw.strip() == "":
            lines.append("")
            continue
        lines.extend(
            textwrap.wrap(raw, width=width, break_long_words=False, break_on_hyphens=False)
        )
    return lines or [""]


def render_box(
    lines: List[str],
    width: int,
    styler: "Styler",
    border_color: str,
    title: str | None = None,
    title_align: str = "left",
    title_color: str | None = None,
) -> None:
    content_width = width - 4
    top = build_top_border(width, styler, border_color, title, title_align, title_color)
    bottom = styler.apply(border_color, "+" + ("-" * (width - 2)) + "+")
    left = styler.apply(border_color, "|")
    right = styler.apply(border_color, "|")
    print(top)
    for line in lines:
        padded = pad_text(line, content_width)
        print(f"{left} {padded} {right}")
    print(bottom)


def build_top_border(
    width: int,
    styler: "Styler",
    border_color: str,
    title: str | None,
    title_align: str,
    title_color: str | None,
) -> str:
    if not title:
        return styler.apply(border_color, "+" + ("-" * (width - 2)) + "+")
    inner_width = width - 2
    title_text = f" {title} "
    if visible_len(title_text) > inner_width:
        title_text = title_text[:inner_width]
    title_len = visible_len(title_text)
    if title_align == "center":
        left_len = max(0, (inner_width - title_len) // 2)
    elif title_align == "right":
        left_len = max(0, inner_width - title_len)
    else:
        left_len = 1
    right_len = max(0, inner_width - title_len - left_len)
    left_border = styler.apply(border_color, "+")
    right_border = styler.apply(border_color, "+")
    left_dash = styler.apply(border_color, "-" * left_len)
    right_dash = styler.apply(border_color, "-" * right_len)
    title_styled = title_text
    title_color = title_color or border_color
    if title_color:
        title_styled = styler.bold(styler.apply(title_color, title_text))
    return f"{left_border}{left_dash}{title_styled}{right_dash}{right_border}"


def get_terminal_width() -> int:
    columns = shutil.get_terminal_size((100, 20)).columns
    return max(80, min(columns, 140))


def provider_border_color(provider: str) -> str:
    mapping = {"gemini": "blue", "anthropic": "yellow", "openai": "green"}
    return mapping.get(provider, "magenta")


def phase_border_color(title: str) -> str:
    mapping = {"Round 1": "blue", "Round 2 (Rebuttals)": "yellow", "Moderator": "green"}
    return mapping.get(title, "blue")


def phase_note(title: str) -> str:
    mapping = {
        "Round 1": "Initial answers",
        "Round 2 (Rebuttals)": "Rebuttals and improvements",
        "Moderator": "Final synthesis",
    }
    return mapping.get(title, "")


class Styler:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    DIM = "\033[2m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    @classmethod
    def from_mode(cls, mode: str) -> "Styler":
        if mode == "always":
            return cls(True)
        if mode == "never":
            return cls(False)
        return cls(sys.stdout.isatty())

    def wrap(self, text: str, code: str) -> str:
        if not self.enabled:
            return text
        return f"{code}{text}{self.RESET}"

    def bold(self, text: str) -> str:
        return self.wrap(text, self.BOLD)

    def italic(self, text: str) -> str:
        return self.wrap(text, self.ITALIC)

    def dim(self, text: str) -> str:
        return self.wrap(text, self.DIM)

    def red(self, text: str) -> str:
        return self.wrap(text, self.RED)

    def yellow(self, text: str) -> str:
        return self.wrap(text, self.YELLOW)

    def green(self, text: str) -> str:
        return self.wrap(text, self.GREEN)

    def blue(self, text: str) -> str:
        return self.wrap(text, self.BLUE)

    def magenta(self, text: str) -> str:
        return self.wrap(text, self.MAGENTA)

    def cyan(self, text: str) -> str:
        return self.wrap(text, self.CYAN)

    def apply(self, color: str, text: str) -> str:
        if not color:
            return text
        color_fn = getattr(self, color, None)
        if not color_fn:
            return text
        return color_fn(text)


if __name__ == "__main__":
    main()
