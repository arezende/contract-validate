"""Disk cache, retry with exponential backoff, and robust JSON parser."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import pathlib
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_FILE = pathlib.Path(__file__).parent.parent.parent / "cache" / "llm_cache.jsonl"

_RETRY_DELAYS = [2, 4, 8, 16]


def _cache_key(model_alias: str, prompt: str, params: dict) -> str:
    payload = json.dumps(
        {"model": model_alias, "prompt": prompt, "params": params},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_cache() -> dict[str, str]:
    if not _CACHE_FILE.exists():
        return {}
    hits: dict[str, str] = {}
    with open(_CACHE_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                hits[entry["key"]] = entry["response"]
            except (json.JSONDecodeError, KeyError):
                pass
    return hits


def _append_cache(key: str, model_alias: str, prompt: str, response: str) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": key,
        "model": model_alias,
        "prompt": prompt,
        "response": response,
        "ts": time.time(),
    }
    with open(_CACHE_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _is_retryable(exc: BaseException) -> bool:
    try:
        import openai
        if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError)):
            return True
        if isinstance(exc, (openai.AuthenticationError, openai.BadRequestError)):
            return False
    except ImportError:
        pass

    if isinstance(exc, httpx.TimeoutException):
        return True

    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if status in (429, 500, 502, 503):
        return True

    return False


async def cached_call(
    adapter_fn,
    prompt: str,
    model_alias: str,
    config: dict,
    params: dict,
) -> str:
    key = _cache_key(model_alias, prompt, params)
    cache = _load_cache()

    if key in cache:
        logger.debug("Cache hit for model=%s key=%s", model_alias, key[:8])
        return cache[key]

    logger.debug("Cache miss for model=%s key=%s", model_alias, key[:8])

    last_exc: BaseException | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.debug(
                "Retry attempt %d for model=%s after %ds", attempt, model_alias, delay
            )
            await asyncio.sleep(delay)
        try:
            response = await adapter_fn(prompt, config, params)
            _append_cache(key, model_alias, prompt, response)
            return response
        except BaseException as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise

    raise last_exc  # type: ignore[misc]


def extract_json(text: str) -> str:
    """Strip ```json ... ``` fences and leading/trailing whitespace."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def parse_json_response(text: str) -> dict | list:
    return json.loads(extract_json(text))
