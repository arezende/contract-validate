"""LLM-only arm — replicates CLAUSE paper Eval_1/2/3 (Choudhury et al., EACL 2026).

Protocol asymmetry (Appendix B):
  Eval_1 — model receives BOTH original and changed document for comparison.
  Eval_2 — model receives ONLY the changed document; forced label output.
  Eval_3 — model receives ONLY the changed document; 4 variants:
            (in_text | legal) × (L1 zero-shot | L2 one-shot).
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
# Prompts — reconstructed from CLAUSE Appendix B (Choudhury et al., EACL 2026)
# Inference params (Appendix A): temperature=0.2, top_p=0.95, max_tokens=8192
# ---------------------------------------------------------------------------

PROMPTS: dict[str, str] = {
    # ------------------------------------------------------------------
    # Eval_1: binary defect detection — single document (CLAUSE §4 protocol).
    # Model must use its own legal knowledge; no reference original provided.
    # Positive instances receive changed_text (perturbed).
    # Negative instances receive original_text (via changed_text = original_text).
    # ------------------------------------------------------------------
    "eval1": """\
You are a US contractual lawyer who answers concisely.

Please read the legal document below in full.

Document:
{changed_text}

Does this document contain any discrepancy? Reply with only "Yes" or "No".""",

    # ------------------------------------------------------------------
    # Eval_2: dimension classification — receives only changed document.
    # Model must output exactly one label; no explanation.
    # ------------------------------------------------------------------
    "eval2": """\
You are a US law expert. Review the following contract document and classify \
the type of contradiction it contains.

A contradiction can be one of three types:
- in_text: one part of the document contradicts another part of the same document
- outer_law: the document contradicts a federal, state, or municipal law of the \
United States
- no_contradiction: the document does not appear to contain any contradiction

Contract:
{changed_text}

Classify the document. Reply with exactly one label — "in_text", "outer_law", or \
"no_contradiction" — and nothing else. No explanation.""",

    # ------------------------------------------------------------------
    # Eval_3 (in_text, L1 — zero-shot): span extraction + explanation
    # ------------------------------------------------------------------
    "eval3_intext_l1": """\
You are a senior US attorney and contractual analyst. The following contract \
contains an in-text contradiction — one part of the document contradicts \
another part of the same document.

Discrepancy categories to consider:
- Ambiguity: vague or multi-interpretable language
- Inconsistency: contradictory provisions within the document
- Misaligned Terminology: terms used inconsistently or diverging from standard definitions
- Omission: a required clause or disclosure is missing
- Structural Flaw: cross-reference or organizational issues

Contract:
{changed_text}

Identify all problematic spans. Return exactly a JSON array with no markdown \
and no commentary. Each element must contain:
  "text"        — the exact sentence or span from the contract
  "explanation" — what it contradicts and why

Return [] if nothing is found.""",

    # ------------------------------------------------------------------
    # Eval_3 (in_text, L2 — one-shot): same as L1 + resolved example
    # ------------------------------------------------------------------
    "eval3_intext_l2": """\
You are a senior US attorney and contractual analyst. The following contract \
contains an in-text contradiction — one part of the document contradicts \
another part of the same document.

Discrepancy categories to consider:
- Ambiguity: vague or multi-interpretable language
- Inconsistency: contradictory provisions within the document
- Misaligned Terminology: terms used inconsistently or diverging from standard definitions
- Omission: a required clause or disclosure is missing
- Structural Flaw: cross-reference or organizational issues

Example:
Contract: "Payment shall be due within 30 days of invoice. [...] All outstanding balances are payable within 60 days of receipt of goods."
Output: [{"text": "All outstanding balances are payable within 60 days of receipt of goods.", "explanation": "Contradicts the earlier provision requiring payment within 30 days of invoice, creating an internal inconsistency on payment timing."}]

Contract:
{changed_text}

Identify all problematic spans. Return exactly a JSON array with no markdown \
and no commentary. Each element must contain:
  "text"        — the exact sentence or span from the contract
  "explanation" — what it contradicts and why

Return [] if nothing is found.""",

    # ------------------------------------------------------------------
    # Eval_3 (legal, L1 — zero-shot): span + explanation + law citation
    # ------------------------------------------------------------------
    "eval3_legal_l1": """\
You are a senior US attorney and contractual analyst. The following contract \
contains an outer-law contradiction — a clause that contradicts a federal, \
state, or municipal law of the United States.

Discrepancy categories to consider:
- Ambiguity: vague or multi-interpretable language
- Inconsistency: contradictory provisions
- Misaligned Terminology: terms used inconsistently or diverging from standard definitions
- Omission: a required clause or disclosure is missing
- Structural Flaw: cross-reference or organizational issues

Contract:
{changed_text}

Identify all problematic spans. Return exactly a JSON array with no markdown \
and no commentary. Each element must contain:
  "text"        — the exact sentence or span from the contract
  "explanation" — what it contradicts and why
  "law"         — the specific statute, regulation, or case violated (or "N/A")

Return [] if nothing is found.""",

    # ------------------------------------------------------------------
    # Eval_3 (legal, L2 — one-shot): same as L1 + resolved example
    # ------------------------------------------------------------------
    "eval3_legal_l2": """\
You are a senior US attorney and contractual analyst. The following contract \
contains an outer-law contradiction — a clause that contradicts a federal, \
state, or municipal law of the United States.

Discrepancy categories to consider:
- Ambiguity: vague or multi-interpretable language
- Inconsistency: contradictory provisions
- Misaligned Terminology: terms used inconsistently or diverging from standard definitions
- Omission: a required clause or disclosure is missing
- Structural Flaw: cross-reference or organizational issues

Example:
Contract: "Employees shall work up to 50 hours per week at their standard hourly rate with no additional compensation for hours exceeding 40."
Output: [{"text": "Employees shall work up to 50 hours per week at their standard hourly rate with no additional compensation for hours exceeding 40.", "explanation": "Requires unpaid overtime in violation of the mandatory time-and-a-half premium for hours beyond 40 in a workweek.", "law": "Fair Labor Standards Act, 29 U.S.C. § 207(a)(1)"}]

Contract:
{changed_text}

Identify all problematic spans. Return exactly a JSON array with no markdown \
and no commentary. Each element must contain:
  "text"        — the exact sentence or span from the contract
  "explanation" — what it contradicts and why
  "law"         — the specific statute, regulation, or case violated (or "N/A")

Return [] if nothing is found.""",
}

# eval1 and eval2 have a single canonical prompt; prompt_level is ignored.
_LEVELLESS_TASKS: frozenset[str] = frozenset({"eval1", "eval2"})

# Maps paper output labels for eval2 → internal Dimension schema
_EVAL2_LABEL_MAP: dict[str, str] = {
    "no_contradiction": "none",
    "no contradiction": "none",
    "nocontradiction": "none",
    "outer_law": "legal",
    "outer law": "legal",
    "in_text": "in_text",
    "in-text": "in_text",
    "intext": "in_text",
}


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class LLMPrediction(BaseModel):
    instance_id: str
    model_alias: str
    prompt_level: str            # "l1" or "l2" (always "l1" for eval1/eval2)
    eval_task: str               # "eval1", "eval2", "eval3"
    answer: bool                 # True = defect detected (forced True for eval2)
    dimension: Optional[str]     # "in_text" | "legal" | None
    location: Optional[str]      # first span text (eval3 compat)
    explanation: Optional[str]   # first span explanation (eval3 compat)
    law_citation: Optional[str]  # first span law (eval3 legal compat)
    spans: Optional[list[dict]] = None  # eval3: full span array
    raw_response: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing helpers — one per eval task
# ---------------------------------------------------------------------------


def _parse_eval1(raw: str, base: dict) -> LLMPrediction:
    try:
        answer = raw.strip().lower().startswith("yes")
        return LLMPrediction(
            **base, answer=answer, dimension=None,
            location=None, explanation=None, law_citation=None,
            spans=None, error=None,
        )
    except Exception as exc:
        return LLMPrediction(
            **base, answer=False, dimension=None,
            location=None, explanation=None, law_citation=None,
            spans=None, error=str(exc),
        )


def _parse_eval2(raw: str, base: dict) -> LLMPrediction:
    try:
        text = raw.strip().lower()
        dim = "none"   # default: treat unrecognized response as no_contradiction
        for label, mapped in _EVAL2_LABEL_MAP.items():
            if label in text:
                dim = mapped
                break
        return LLMPrediction(
            **base, answer=(dim != "none"), dimension=dim,
            location=None, explanation=None, law_citation=None,
            spans=None, error=None,
        )
    except Exception as exc:
        return LLMPrediction(
            **base, answer=False, dimension="none",
            location=None, explanation=None, law_citation=None,
            spans=None, error=str(exc),
        )


def _parse_eval3(raw: str, base: dict) -> LLMPrediction:
    try:
        data = parse_json_response(raw)
        spans: list[dict] = data if isinstance(data, list) else []
        answer = len(spans) > 0
        first = spans[0] if spans else {}
        return LLMPrediction(
            **base,
            answer=answer,
            dimension=None,
            location=first.get("text") or None,
            explanation=first.get("explanation") or None,
            law_citation=first.get("law") or None,
            spans=spans or None,
            error=None,
        )
    except Exception as exc:
        logger.warning("Parse failure eval3 instance=%s: %s", base.get("instance_id"), exc)
        return LLMPrediction(
            **base, answer=False, dimension=None,
            location=None, explanation=None, law_citation=None,
            spans=None, error=str(exc),
        )


def _parse_prediction(
    raw: str,
    eval_task: str,
    instance_id: str,
    model_alias: str,
    prompt_level: str,
) -> LLMPrediction:
    base = dict(
        instance_id=instance_id,
        model_alias=model_alias,
        prompt_level=prompt_level,
        eval_task=eval_task,
        raw_response=raw,
    )
    if eval_task == "eval1":
        return _parse_eval1(raw, base)
    elif eval_task == "eval2":
        return _parse_eval2(raw, base)
    else:
        return _parse_eval3(raw, base)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def run_instance(
    instance: DiscrepancyInstance,
    model_alias: str,
    eval_task: str,
    prompt_level: str,
) -> LLMPrediction:
    """Run one instance through the LLM-only arm.

    Protocol (CLAUSE paper §4):
      eval1 — single document only (changed_text). For negatives, create_negatives()
               sets changed_text = original_text, so the model sees the clean contract.
      eval2 — receives only changed_text; prompt_level is ignored.
      eval3 — receives only changed_text; routes on instance.dimension × prompt_level.
    """
    if eval_task == "eval1":
        prompt = PROMPTS["eval1"].format(changed_text=instance.changed_text)
    elif eval_task == "eval2":
        prompt = PROMPTS["eval2"].format(changed_text=instance.changed_text)
    elif eval_task == "eval3":
        dim_key = "intext" if instance.dimension == "in_text" else "legal"
        prompt_key = f"eval3_{dim_key}_{prompt_level}"
        if prompt_key not in PROMPTS:
            raise ValueError(f"Unknown prompt key '{prompt_key}'")
        prompt = PROMPTS[prompt_key].format(changed_text=instance.changed_text)
    else:
        raise ValueError(
            f"Unknown eval_task '{eval_task}'. Valid: eval1, eval2, eval3."
        )

    raw = await generate(prompt, model_alias)
    return _parse_prediction(
        raw=raw,
        eval_task=eval_task,
        instance_id=instance.instance_id,
        model_alias=model_alias,
        prompt_level=prompt_level,
    )


async def run_batch(
    instances: list[DiscrepancyInstance],
    model_aliases: list[str],
    eval_tasks: list[str],
    prompt_levels: list[str],
    max_concurrent: int = 1,
) -> list[LLMPrediction]:
    """Run all (instance × model × task × level) combinations.

    For eval1 and eval2 (levelless tasks) only one call is made per instance
    regardless of prompt_levels; the level is stored as 'l1'.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _bounded(
        instance: DiscrepancyInstance,
        model_alias: str,
        eval_task: str,
        prompt_level: str,
    ) -> LLMPrediction:
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
                    spans=None,
                    raw_response="",
                    error=str(exc),
                )

    tasks = []
    for instance in instances:
        for model_alias in model_aliases:
            for eval_task in eval_tasks:
                levels = ["l1"] if eval_task in _LEVELLESS_TASKS else prompt_levels
                for prompt_level in levels:
                    tasks.append(_bounded(instance, model_alias, eval_task, prompt_level))

    results = list(await asyncio.gather(*tasks))
    errors = sum(1 for r in results if r.error)
    if errors:
        logger.warning("%d/%d calls failed", errors, len(results))
    return results


def run_batch_sync(
    instances: list[DiscrepancyInstance],
    model_aliases: list[str],
    eval_tasks: list[str],
    prompt_levels: list[str],
    max_concurrent: int = 1,
) -> list[LLMPrediction]:
    """Synchronous wrapper for run_batch."""
    return asyncio.run(
        run_batch(instances, model_aliases, eval_tasks, prompt_levels, max_concurrent)
    )
