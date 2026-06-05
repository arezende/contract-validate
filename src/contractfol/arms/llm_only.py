"""LLM-only arm — replicates CLAUSE paper Eval_1/2/3 at prompt levels L1/L2.

Objective A: reproduce paper numbers on original models (GPT-4o, Gemini, etc.)
Objective B: extend to new models (Qwen, DeepSeek, Kimi) for new baselines.

Reference: Choudhury et al., EACL 2026, arXiv:2511.00340
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel

from contractfol.corpus.schema import DiscrepancyInstance
from contractfol.llm.cache import parse_json_response
from contractfol.llm.interface import generate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts — faithful reconstructions of the CLAUSE paper appendix prompts.
# Swap exact text here once the controlled-access appendix is obtained.
# ---------------------------------------------------------------------------

PROMPTS: dict[str, str] = {
    "eval1_l1": """\
You are a legal contract auditor. Review the following contract text and determine whether it contains a discrepancy, inconsistency, ambiguity, omission, misaligned terminology, or structural flaw.

Contract text:
{changed_text}

Does this contract contain a discrepancy? Answer with a JSON object:
{{"answer": "Yes"}} if a discrepancy is present, or {{"answer": "No"}} if the contract is sound.""",  # NOTE: verify against CLAUSE appendix

    "eval1_l2": """\
You are a legal contract auditor. Review the following contract text and determine whether it contains any of these discrepancy types:
- Ambiguity: unclear or multiple interpretations possible
- Inconsistency: contradictory terms or clauses
- Misaligned Terminology: terms used inconsistently or diverging from standard definitions
- Omission: required clause or disclosure is missing
- Structural Flaw: organizational or cross-reference issues

Contract text:
{changed_text}

Does this contract contain a discrepancy? Answer with a JSON object:
{{"answer": "Yes"}} if a discrepancy is present, or {{"answer": "No"}} if the contract is sound.""",  # NOTE: verify against CLAUSE appendix

    "eval2_l1": """\
You are a legal contract auditor. Review the following contract text and classify any discrepancy you find.

Contract text:
{changed_text}

If a discrepancy exists, is it:
- "in_text": an internal inconsistency within the contract itself
- "legal": a violation of an external legal requirement or statute

Answer with a JSON object: {{"answer": "Yes", "dimension": "in_text"}} or {{"answer": "Yes", "dimension": "legal"}} or {{"answer": "No", "dimension": null}}""",  # NOTE: verify against CLAUSE appendix

    "eval2_l2": """\
You are a legal contract auditor. Review the following contract text.

A discrepancy can be:
- In-text (internal): contradictions, ambiguities, or structural flaws within the contract
- Legal (external): clauses that violate statutory requirements, regulatory provisions, or established legal standards

Contract text:
{changed_text}

Classify any discrepancy found. Answer with a JSON object:
{{"answer": "Yes", "dimension": "in_text"}} or {{"answer": "Yes", "dimension": "legal"}} or {{"answer": "No", "dimension": null}}""",  # NOTE: verify against CLAUSE appendix

    "eval3_l1": """\
You are a legal contract auditor. Review the following contract text.

Contract text:
{changed_text}

If a discrepancy exists:
1. Identify the specific location (quote the relevant span verbatim)
2. Explain the nature of the discrepancy
3. If the discrepancy involves a legal violation, cite the relevant law or statute

Answer with a JSON object:
{{
  "answer": "Yes",
  "location": "<quoted span>",
  "explanation": "<explanation>",
  "law_citation": "<citation or null>"
}}
Or if no discrepancy: {{"answer": "No", "location": null, "explanation": null, "law_citation": null}}""",  # NOTE: verify against CLAUSE appendix

    "eval3_l2": """\
You are a legal contract auditor specializing in commercial contracts under US law. Review the following contract text.

Discrepancy types to look for:
- Ambiguity: vague or multi-interpretable language
- Inconsistency: contradictory provisions
- Misaligned Terminology: non-standard or inconsistently defined terms
- Omission: missing required clauses or disclosures
- Structural Flaw: cross-reference or organizational issues

Contract text:
{changed_text}

If a discrepancy exists, provide:
1. The exact location (verbatim quote of the problematic span)
2. A clear explanation referencing the specific type of discrepancy
3. For legal discrepancies, cite the violated statute or regulation (e.g., "15 U.S.C. § 1681")

Answer with a JSON object:
{{
  "answer": "Yes",
  "dimension": "in_text",
  "location": "<quoted span>",
  "explanation": "<explanation>",
  "law_citation": "<citation or null>"
}}
Or if no discrepancy: {{"answer": "No", "dimension": null, "location": null, "explanation": null, "law_citation": null}}""",  # NOTE: verify against CLAUSE appendix
}


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class LLMPrediction(BaseModel):
    instance_id: str
    model_alias: str
    prompt_level: str           # "l1" or "l2"
    eval_task: str              # "eval1", "eval2", "eval3"
    answer: bool                # True = defect detected
    dimension: Optional[str]    # "in_text" | "legal" | None
    location: Optional[str]     # predicted span
    explanation: Optional[str]  # predicted explanation
    law_citation: Optional[str] # predicted citation
    raw_response: str           # full LLM output for debugging
    error: Optional[str] = None # if parsing failed


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_prediction(
    raw: str,
    instance_id: str,
    model_alias: str,
    eval_task: str,
    prompt_level: str,
) -> LLMPrediction:
    """Parse LLM raw JSON response into an LLMPrediction.

    On any parse failure: answer=False (conservative — treat as non-detection),
    error set to the exception message.
    """
    base = dict(
        instance_id=instance_id,
        model_alias=model_alias,
        prompt_level=prompt_level,
        eval_task=eval_task,
        raw_response=raw,
    )
    try:
        data = parse_json_response(raw)
        answer_str = data.get("answer", "No")
        answer: bool = str(answer_str).strip().lower() in ("yes", "true", "1")
        return LLMPrediction(
            **base,
            answer=answer,
            dimension=data.get("dimension") or None,
            location=data.get("location") or None,
            explanation=data.get("explanation") or None,
            law_citation=data.get("law_citation") or None,
            error=None,
        )
    except Exception as exc:
        logger.warning(
            "Parse failure for instance=%s model=%s task=%s level=%s: %s",
            instance_id, model_alias, eval_task, prompt_level, exc,
        )
        return LLMPrediction(
            **base,
            answer=False,
            dimension=None,
            location=None,
            explanation=None,
            law_citation=None,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def run_instance(
    instance: DiscrepancyInstance,
    model_alias: str,
    eval_task: str,
    prompt_level: str,
) -> LLMPrediction:
    """Run a single instance through the LLM-only arm.

    Args:
        instance:     A DiscrepancyInstance from the corpus.
        model_alias:  Registry alias (e.g. "gpt-4o-mini", "qwen-plus").
        eval_task:    One of "eval1", "eval2", "eval3".
        prompt_level: One of "l1", "l2".

    Returns:
        LLMPrediction with parsed fields, or error set if parsing failed.
    """
    prompt_key = f"{eval_task}_{prompt_level}"
    if prompt_key not in PROMPTS:
        raise ValueError(
            f"Unknown prompt key '{prompt_key}'. "
            f"Valid keys: {sorted(PROMPTS)}"
        )

    prompt = PROMPTS[prompt_key].format(changed_text=instance.changed_text)

    raw = await generate(prompt, model_alias)

    return _parse_prediction(
        raw=raw,
        instance_id=instance.instance_id,
        model_alias=model_alias,
        eval_task=eval_task,
        prompt_level=prompt_level,
    )


async def run_batch(
    instances: list[DiscrepancyInstance],
    model_aliases: list[str],
    eval_tasks: list[str],
    prompt_levels: list[str],
    max_concurrent: int = 5,
) -> list[LLMPrediction]:
    """Run all combinations of (instance × model × task × level).

    Uses asyncio.Semaphore(max_concurrent) to avoid rate-limit bursts.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _bounded(instance, model_alias, eval_task, prompt_level):
        async with semaphore:
            try:
                return await run_instance(instance, model_alias, eval_task, prompt_level)
            except Exception as exc:
                logger.error(
                    "API error — instance=%s model=%s task=%s level=%s: %s",
                    instance.instance_id, model_alias, eval_task, prompt_level, exc,
                )
                return LLMPrediction(
                    instance_id=instance.instance_id,
                    model_alias=model_alias,
                    prompt_level=prompt_level,
                    eval_task=eval_task,
                    answer=False,
                    dimension=None,
                    location=None,
                    explanation=None,
                    law_citation=None,
                    raw_response="",
                    error=str(exc),
                )

    tasks = [
        _bounded(instance, model_alias, eval_task, prompt_level)
        for instance in instances
        for model_alias in model_aliases
        for eval_task in eval_tasks
        for prompt_level in prompt_levels
    ]

    results = await asyncio.gather(*tasks)
    errors = sum(1 for r in results if r.error)
    if errors:
        logger.warning("%d/%d calls failed (see error field in predictions)", errors, len(results))
    return list(results)


def run_batch_sync(
    instances: list[DiscrepancyInstance],
    model_aliases: list[str],
    eval_tasks: list[str],
    prompt_levels: list[str],
    max_concurrent: int = 5,
) -> list[LLMPrediction]:
    """Synchronous wrapper for run_batch."""
    return asyncio.run(
        run_batch(instances, model_aliases, eval_tasks, prompt_levels, max_concurrent)
    )
