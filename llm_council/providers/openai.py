from __future__ import annotations

from typing import Any, Dict, List

import requests

from .base import ChatResult, Provider, ProviderError


class OpenAIProvider(Provider):
    name = "openai"

    def list_models(self, api_key: str, base_url: str, timeout_s: int) -> List[str]:
        url = f"{base_url}/models"
        headers = {"authorization": f"Bearer {api_key}"}
        try:
            response = requests.get(url, headers=headers, timeout=timeout_s)
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"OpenAI list models failed: {response.status_code} {response.text}")
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
        url = f"{base_url}/responses"
        headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
        input_messages = []
        for message in messages:
            input_messages.append(
                {
                    "role": message["role"],
                    "content": [{"type": "text", "text": message["content"]}],
                }
            )
        payload: Dict[str, Any] = {
            "model": model,
            "input": input_messages,
        }
        if "max_output_tokens" in request_cfg:
            payload["max_output_tokens"] = request_cfg["max_output_tokens"]
        if "temperature" in request_cfg:
            payload["temperature"] = request_cfg["temperature"]
        if provider_cfg.get("reasoning"):
            payload["reasoning"] = provider_cfg["reasoning"]
        payload.update(provider_cfg.get("request_overrides", {}))
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=request_cfg.get("timeout_s", 60))
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"OpenAI chat failed: {response.status_code} {response.text}")
        data = response.json()
        if "output_text" in data:
            return ChatResult(text=data.get("output_text", ""), raw=data)
        text_parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if "text" in content:
                    text_parts.append(content["text"])
        return ChatResult(text="".join(text_parts), raw=data)
