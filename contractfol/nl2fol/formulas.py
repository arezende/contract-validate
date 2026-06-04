"""
Step 4.2 — NormElement extraction via LLM → RIN.

Calls the LLM with the formula-extraction prompt (given the symbol vocabulary
from Step 4.1) and assembles a RIN object from the parsed NormElement list.
"""

from __future__ import annotations

import asyncio
import logging

from contractfol.llm.interface import generate
from contractfol.llm.cache import parse_json_response
from contractfol.nl2fol.prompts import formula_extraction_prompt
from contractfol.rin.schema import RIN, NormElement, Symbol

logger = logging.getLogger(__name__)


async def extract_rin(
    clause_text: str,
    symbols: list[Symbol],
    instance_id: str,
    variant: str,  # "original" | "changed"
    model_alias: str,
) -> RIN:
    """
    Step 4.2: Ask the LLM to extract NormElements given the symbol vocabulary.
    Returns a RIN object.
    Raises ValueError if the LLM returns zero valid elements (translation failure).
    """
    prompt = formula_extraction_prompt(
        clause_text, [s.model_dump() for s in symbols]
    )

    raw = await generate(prompt, model_alias)

    try:
        items = parse_json_response(raw)
    except Exception as exc:
        raise ValueError(
            f"Translation failure for {instance_id}/{variant}: "
            f"Failed to parse JSON from formula extraction response: {exc}"
        ) from exc

    if not isinstance(items, list):
        raise ValueError(
            f"Translation failure for {instance_id}/{variant}: "
            f"Formula extraction expected a JSON array, got {type(items).__name__}"
        )

    elements: list[NormElement] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning(
                "NormElement item %d is not a dict, skipping: %r", i, item
            )
            continue
        try:
            elem = NormElement(**item)
            elements.append(elem)
        except Exception as exc:
            logger.warning(
                "NormElement item %d failed validation, skipping: %s", i, exc
            )

    if not elements:
        raise ValueError(
            f"Translation failure for {instance_id}/{variant}: "
            "LLM returned no valid NormElements"
        )

    return RIN(
        instance_id=instance_id,
        variant=variant,  # type: ignore[arg-type]
        symbols=symbols,
        elements=elements,
        translator_model=model_alias,
    )


def extract_rin_sync(
    clause_text: str,
    symbols: list[Symbol],
    instance_id: str,
    variant: str,
    model_alias: str,
) -> RIN:
    """Sync wrapper."""
    return asyncio.run(
        extract_rin(clause_text, symbols, instance_id, variant, model_alias)
    )
