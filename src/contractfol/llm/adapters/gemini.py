"""Adapter for Google Gemini via google-generativeai SDK."""

from __future__ import annotations

import asyncio
import os

import google.generativeai as genai


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
    genai.configure(api_key=_resolve_api_key())

    merged = {
        "temperature":      config.get("temperature", 0.2),
        "top_p":            config.get("top_p", 0.95),
        "max_output_tokens": config.get("max_tokens", 8192),
    }
    if "temperature" in params:
        merged["temperature"] = params["temperature"]
    if "top_p" in params:
        merged["top_p"] = params["top_p"]
    if "max_tokens" in params:
        merged["max_output_tokens"] = params["max_tokens"]
    merged.update(_env_param_overrides())

    model = genai.GenerativeModel(
        model_name=os.getenv("CONTRACTFOL_MODEL") or config["model_id"],
        generation_config=genai.types.GenerationConfig(**merged),
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    return response.text
