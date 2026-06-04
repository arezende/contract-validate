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
    key = os.getenv(env_var) or os.getenv("OPENAI_API_KEY", "")
    return key


async def call(prompt: str, config: dict, params: dict) -> str:
    base_url: str = config["base_url"]
    api_key = _resolve_api_key(base_url)

    merged = {
        "model": config["model_id"],
        "temperature": config.get("temperature", 0.2),
        "top_p": config.get("top_p", 1.0),
        "max_tokens": config.get("max_tokens", 8192),
    }
    merged.update(params)

    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
    response = await client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        **merged,
    )
    return response.choices[0].message.content
