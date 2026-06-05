"""Adapter for any OpenAI-compatible API endpoint."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import openai

_DOMAIN_TO_ENV: dict[str, str] = {
    "api.openai.com": "OPENAI_API_KEY",
    "api.groq.com": "GROQ_API_KEY",
    "api.deepseek.com": "DEEPSEEK_API_KEY",
    "api.moonshot.cn": "MOONSHOT_API_KEY",
    "dashscope.aliyuncs.com": "DASHSCOPE_API_KEY",
}


def _resolve_api_key(base_url: str) -> str:
    domain = urlparse(base_url).hostname or ""
    env_var = _DOMAIN_TO_ENV.get(domain, "OPENAI_API_KEY")
    return (
        os.getenv(env_var)
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("CONTRACTFOL_API_KEY")
        or ""
    )


def _env_param_overrides() -> dict:
    """Read CONTRACTFOL_* env vars that override per-call parameters."""
    overrides: dict = {}
    if (t := os.getenv("CONTRACTFOL_TEMPERATURE")) is not None:
        overrides["temperature"] = float(t)
    if (m := os.getenv("CONTRACTFOL_MAX_TOKENS")) is not None:
        overrides["max_tokens"] = int(m)
    return overrides


async def call(prompt: str, config: dict, params: dict) -> str:
    base_url: str = config["base_url"]
    api_key = _resolve_api_key(base_url)

    merged = {
        "model": os.getenv("CONTRACTFOL_MODEL") or config["model_id"],
        "temperature": config.get("temperature", 0.2),
        "top_p": config.get("top_p", 1.0),
        "max_tokens": config.get("max_tokens", 8192),
    }
    merged.update(_env_param_overrides())  # env overrides before CLI params
    merged.update(params)                  # CLI params win

    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
    response = await client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        **merged,
    )
    return response.choices[0].message.content
