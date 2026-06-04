"""Public interface for LLM generation — async-first with a sync convenience shim."""

from __future__ import annotations

import asyncio
import importlib

from contractfol.llm.cache import cached_call
from contractfol.llm.registry import get_model_config

_ADAPTER_MODULE = {
    "openai_compatible": "contractfol.llm.adapters.openai_compatible",
    "gemini": "contractfol.llm.adapters.gemini",
}


async def generate(
    prompt: str,
    model_alias: str,
    params: dict | None = None,
) -> str:
    config = get_model_config(model_alias)
    adapter_name = config["adapter"]

    module_path = _ADAPTER_MODULE.get(adapter_name)
    if module_path is None:
        raise ValueError(f"Unknown adapter '{adapter_name}' for model '{model_alias}'")

    module = importlib.import_module(module_path)
    resolved_params = {
        k: v
        for k, v in (params or {}).items()
        if k in {"temperature", "top_p", "max_tokens"}
    }

    return await cached_call(module.call, prompt, model_alias, config, resolved_params)


def generate_sync(
    prompt: str,
    model_alias: str,
    params: dict | None = None,
) -> str:
    return asyncio.run(generate(prompt, model_alias, params))
