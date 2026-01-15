from __future__ import annotations

from typing import Any, Dict, List

import requests

from .base import ChatResult, Provider, ProviderError


class AnthropicProvider(Provider):
    name = "anthropic"

    def list_models(self, api_key: str, base_url: str, timeout_s: int) -> List[str]:
        url = f"{base_url}/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        try:
            response = requests.get(url, headers=headers, timeout=timeout_s)
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"Anthropic list models failed: {response.status_code} {response.text}")
        data = response.json()
        models = [item.get("id", "") for item in data.get("data", [])]
        return sorted([m for m in models if m])

    def chat(
        self,
        api_key: str,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        request_cfg: Dict[str, Any],
        provider_cfg: Dict[str, Any],
    ) -> ChatResult:
        url = f"{base_url}/messages"
        system_text = ""
        payload_messages = []
        for message in messages:
            role = message["role"]
            if role == "system":
                system_text = message["content"]
                continue
            payload_messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": message["content"]}],
                }
            )
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": request_cfg.get("max_output_tokens", 1024),
            "temperature": request_cfg.get("temperature", 0.2),
            "messages": payload_messages,
        }
        if system_text:
            payload["system"] = system_text
        if provider_cfg.get("thinking"):
            payload["thinking"] = provider_cfg["thinking"]
        payload.update(provider_cfg.get("request_overrides", {}))
        headers = {
            "x-api-key": api_key,
            "anthropic-version": provider_cfg.get("version", "2023-06-01"),
            "content-type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=request_cfg.get("timeout_s", 60))
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"Anthropic chat failed: {response.status_code} {response.text}")
        data = response.json()
        content_blocks = data.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return ChatResult(text="".join(text_parts), raw=data)
