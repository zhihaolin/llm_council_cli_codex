from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


class ProviderError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    raw: Dict[str, Any]


class Provider:
    name: str = ""

    def list_models(self, api_key: str, base_url: str, timeout_s: int) -> List[str]:
        raise NotImplementedError

    def chat(
        self,
        api_key: str,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        request_cfg: Dict[str, Any],
        provider_cfg: Dict[str, Any],
    ) -> ChatResult:
        raise NotImplementedError
