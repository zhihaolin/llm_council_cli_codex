from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider


def get_provider(name: str):
    name = name.lower()
    if name == "gemini":
        return GeminiProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown provider: {name}")
