"""Adapter for Google Gemini via google-genai SDK (v1+)."""

from __future__ import annotations

import os

from google import genai
from google.genai import types


def _resolve_api_key() -> str:
    return (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("CONTRACTFOL_API_KEY")
        or ""
    )


def _env_param_overrides() -> dict:
    overrides: dict = {}
    if (t := os.getenv("CONTRACTFOL_TEMPERATURE")) is not None:
        overrides["temperature"] = float(t)
    if (m := os.getenv("CONTRACTFOL_MAX_TOKENS")) is not None:
        overrides["max_output_tokens"] = int(m)
    return overrides


async def call(prompt: str, config: dict, params: dict) -> str:
    client = genai.Client(api_key=_resolve_api_key())

    merged = {
        "temperature":       config.get("temperature", 0.2),
        "top_p":             config.get("top_p", 0.95),
        "max_output_tokens": config.get("max_tokens", 8192),
    }
    if "temperature" in params:
        merged["temperature"] = params["temperature"]
    if "top_p" in params:
        merged["top_p"] = params["top_p"]
    if "max_tokens" in params:
        merged["max_output_tokens"] = params["max_tokens"]
    merged.update(_env_param_overrides())

    model_id = os.getenv("CONTRACTFOL_MODEL") or config["model_id"]

    response = await client.aio.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(**merged),
    )
    return response.text
