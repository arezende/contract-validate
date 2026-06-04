"""Semantic citation comparison using Gemini as a paralegal judge."""

from __future__ import annotations

from contractfol.llm.cache import parse_json_response
from contractfol.llm.interface import generate_sync

_JUDGE_ALIAS = "gemini-2.5-flash"
_JUDGE_PARAMS = {"temperature": 0.0}

_PROMPT_TEMPLATE = """\
You are a paralegal assistant. Determine if the following two legal citations refer to the same statutory provision or legal rule.

Citation A: {pred_citation}
Citation B: {gt_citation}

Consider them a match if they refer to the same section, subsection, or equivalent provision, even if the formatting differs.

Respond with only: {{"match": true}} or {{"match": false}}"""


def _build_prompt(pred_citation: str, gt_citation: str) -> str:
    return _PROMPT_TEMPLATE.format(
        pred_citation=pred_citation,
        gt_citation=gt_citation,
    )


def law_match(
    pred_citation: str | None,
    gt_citation: str | None,
) -> bool:
    """
    Returns True if pred_citation refers to the same legal provision as gt_citation.
    Uses Gemini-2.5-flash as a paralegal judge.
    Returns False if either citation is None.
    """
    if pred_citation is None or gt_citation is None:
        return False

    prompt = _build_prompt(pred_citation, gt_citation)
    raw = generate_sync(prompt, _JUDGE_ALIAS, _JUDGE_PARAMS)
    result = parse_json_response(raw)
    return bool(result.get("match", False))


def law_match_batch(
    pred_citations: list[str | None],
    gt_citations: list[str | None],
) -> list[bool]:
    """Batch version — runs sequentially to respect rate limits."""
    if len(pred_citations) != len(gt_citations):
        raise ValueError("pred_citations and gt_citations must have the same length.")
    return [law_match(p, g) for p, g in zip(pred_citations, gt_citations)]


def law_match_accuracy(
    pred_citations: list[str | None],
    gt_citations: list[str | None],
) -> float:
    """Fraction of instances where law_match is True. Only counts legal-dimension instances (non-None GT)."""
    if len(pred_citations) != len(gt_citations):
        raise ValueError("pred_citations and gt_citations must have the same length.")

    legal_instances = [
        (p, g) for p, g in zip(pred_citations, gt_citations) if g is not None
    ]
    if not legal_instances:
        return 0.0

    matches = sum(
        1 for p, g in legal_instances if law_match(p, g)
    )
    return matches / len(legal_instances)
