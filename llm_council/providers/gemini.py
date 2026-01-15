from __future__ import annotations

from typing import Any, Dict, List

import requests

from .base import ChatResult, Provider, ProviderError


class GeminiProvider(Provider):
    name = "gemini"

    def list_models(self, api_key: str, base_url: str, timeout_s: int) -> List[str]:
        url = f"{base_url}/models?key={api_key}"
        try:
            response = requests.get(url, timeout=timeout_s)
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"Gemini list models failed: {response.status_code} {response.text}")
        data = response.json()
        models = []
        for model in data.get("models", []):
            name = model.get("name", "")
            if name.startswith("models/"):
                name = name.split("/", 1)[1]
            models.append(name)
        return sorted(models)

    def chat(
        self,
        api_key: str,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        request_cfg: Dict[str, Any],
        provider_cfg: Dict[str, Any],
    ) -> ChatResult:
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        contents = []
        system_text = None
        for message in messages:
            role = message["role"]
            if role == "system":
                system_text = message["content"]
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": message["content"]}]})
        payload: Dict[str, Any] = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        generation_config: Dict[str, Any] = {}
        if "temperature" in request_cfg:
            generation_config["temperature"] = request_cfg["temperature"]
        if "max_output_tokens" in request_cfg:
            generation_config["maxOutputTokens"] = request_cfg["max_output_tokens"]
        generation_config.update(provider_cfg.get("generation_config", {}))
        if generation_config:
            payload["generationConfig"] = generation_config
        payload.update(provider_cfg.get("request_overrides", {}))
        try:
            response = requests.post(url, json=payload, timeout=request_cfg.get("timeout_s", 60))
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if not response.ok:
            raise ProviderError(f"Gemini chat failed: {response.status_code} {response.text}")
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError("Gemini chat returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = ""
        if parts:
            text = parts[0].get("text", "")
        return ChatResult(text=text, raw=data)
