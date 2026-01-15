from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any, Dict, List

from .config import resolve_api_key
from .providers import get_provider
from .providers.base import ProviderError


ROUND1_SYSTEM = (
    "You are a council member. Provide a direct, opinionated answer. "
    "Be concise, practical, and avoid hedging unless needed."
)

ROUND2_SYSTEM = (
    "You are a council member in a debate. Critique other responses, identify "
    "weaknesses, and provide your improved stance. Avoid repeating your round 1 answer."
)

MODERATOR_SYSTEM = (
    "You are the council moderator. Synthesize a final answer that resolves "
    "disagreements, highlights tradeoffs, and ends with clear recommendations."
)


@dataclass
class Member:
    provider: str
    model: str

    def label(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass
class MemberReply:
    member: Member
    text: str
    error: str | None = None


@dataclass
class DebateResult:
    prompt: str
    round1: List[MemberReply]
    round2: List[MemberReply]
    moderator: MemberReply | None


def resolve_members(cfg: Dict[str, Any]) -> List[Member]:
    members = []
    for name in cfg.get("council", {}).get("members", []):
        provider_cfg = cfg.get("providers", {}).get(name, {})
        model = provider_cfg.get("model", "")
        members.append(Member(provider=name, model=model))
    return members


def run_debate(prompt: str, cfg: Dict[str, Any]) -> DebateResult:
    request_cfg = cfg.get("request", {})
    members = resolve_members(cfg)
    if not members:
        raise ValueError("No council members configured.")
    round1 = []
    for member in members:
        announce_call("Round 1", member)
        reply = call_member(member, prompt, ROUND1_SYSTEM, request_cfg, cfg)
        round1.append(reply)
    round2 = []
    for member in members:
        other_responses = [
            f"- {reply.member.label()}: {reply.text}"
            for reply in round1
            if reply.member.provider != member.provider
        ]
        rebuttal_prompt = "\n".join(
            [
                f"User question:\n{prompt}",
                "",
                "Other council responses:",
                *other_responses,
                "",
                "Provide your rebuttal and improved answer.",
            ]
        )
        announce_call("Round 2", member)
        reply = call_member(member, rebuttal_prompt, ROUND2_SYSTEM, request_cfg, cfg)
        round2.append(reply)

    moderator_cfg = cfg.get("moderator", {})
    moderator_member = Member(
        provider=moderator_cfg.get("provider", members[0].provider if members else ""),
        model=moderator_cfg.get("model", ""),
    )
    moderator_prompt = "\n".join(
        [
            f"User question:\n{prompt}",
            "",
            "Round 1 responses:",
            *[f"- {reply.member.label()}: {reply.text}" for reply in round1],
            "",
            "Round 2 rebuttals:",
            *[f"- {reply.member.label()}: {reply.text}" for reply in round2],
            "",
            "Synthesize the final answer.",
        ]
    )
    announce_call("Moderator", moderator_member)
    moderator_reply = call_member(
        moderator_member, moderator_prompt, MODERATOR_SYSTEM, request_cfg, cfg
    )
    return DebateResult(prompt=prompt, round1=round1, round2=round2, moderator=moderator_reply)


def call_member(
    member: Member,
    user_prompt: str,
    system_prompt: str,
    request_cfg: Dict[str, Any],
    cfg: Dict[str, Any],
) -> MemberReply:
    provider_cfg = cfg.get("providers", {}).get(member.provider, {})
    api_key = resolve_api_key(provider_cfg)
    if not api_key:
        return MemberReply(
            member=member,
            text="",
            error=f"Missing API key for {member.provider}.",
        )
    model = member.model or provider_cfg.get("model", "")
    if not model:
        return MemberReply(
            member=member,
            text="",
            error=f"Missing model for {member.provider}.",
        )
    provider = get_provider(member.provider)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        result = provider.chat(
            api_key=api_key,
            base_url=provider_cfg.get("base_url", ""),
            model=model,
            messages=messages,
            request_cfg=request_cfg,
            provider_cfg=provider_cfg,
        )
        return MemberReply(member=member, text=result.text)
    except ProviderError as exc:
        return MemberReply(member=member, text="", error=str(exc))


def announce_call(stage: str, member: Member) -> None:
    print(f"{stage} -> {member.label()}", file=sys.stderr, flush=True)
