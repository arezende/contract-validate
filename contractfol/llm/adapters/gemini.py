"""Adapter for Google Gemini via google-generativeai SDK."""

from __future__ import annotations

import asyncio
import os

import google.generativeai as genai


async def call(prompt: str, config: dict, params: dict) -> str:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))

    generation_config = genai.types.GenerationConfig(
        temperature=params.get("temperature", config.get("temperature", 0.2)),
        top_p=params.get("top_p", config.get("top_p", 0.95)),
        max_output_tokens=params.get("max_tokens", config.get("max_tokens", 8192)),
    )

    model = genai.GenerativeModel(
        model_name=config["model_id"],
        generation_config=generation_config,
    )

    # The google-generativeai SDK is synchronous; run it in an executor to avoid
    # blocking the event loop.
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    return response.text
