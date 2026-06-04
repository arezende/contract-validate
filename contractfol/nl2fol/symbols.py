"""
Step 4.1 — Symbol extraction via LLM.

Calls the LLM with the symbol-extraction prompt and parses the response
into a list of Symbol objects.
"""

from __future__ import annotations

import asyncio
import logging

from contractfol.llm.interface import generate
from contractfol.llm.cache import parse_json_response
from contractfol.nl2fol.prompts import symbol_extraction_prompt
from contractfol.rin.schema import Symbol

logger = logging.getLogger(__name__)


async def extract_symbols(
    clause_text: str,
    model_alias: str,
) -> list[Symbol]:
    """
    Step 4.1: Ask the LLM to identify symbols in the clause.
    Returns a list of Symbol objects.
    On parse failure, logs error and returns empty list.
    """
    prompt = symbol_extraction_prompt(clause_text)

    try:
        raw = await generate(prompt, model_alias)
    except Exception as exc:
        logger.error("LLM call failed during symbol extraction: %s", exc)
        return []

    try:
        items = parse_json_response(raw)
    except Exception as exc:
        logger.error(
            "Failed to parse JSON from symbol extraction response: %s\nRaw: %r",
            exc,
            raw[:500],
        )
        return []

    if not isinstance(items, list):
        logger.error(
            "Symbol extraction expected a JSON array, got %s", type(items).__name__
        )
        return []

    symbols: list[Symbol] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning("Symbol item %d is not a dict, skipping: %r", i, item)
            continue
        try:
            sym = Symbol(**item)
            symbols.append(sym)
        except Exception as exc:
            logger.warning("Symbol item %d failed validation, skipping: %s", i, exc)

    return symbols


def extract_symbols_sync(clause_text: str, model_alias: str) -> list[Symbol]:
    """Sync wrapper."""
    return asyncio.run(extract_symbols(clause_text, model_alias))
