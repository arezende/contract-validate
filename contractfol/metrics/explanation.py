"""Dual-judge explanation scoring using LLM-as-judge (GPT-4o + Gemini-2.5)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from contractfol.llm.cache import parse_json_response
from contractfol.llm.interface import generate, generate_sync

# Judge model aliases (must be present in models.yaml)
_JUDGE1_ALIAS = "gpt-4o"         # GPT-4o-2024-08-06
_JUDGE2_ALIAS = "gemini-2.5-flash"  # gemini-2.5-flash-002

_JUDGE_PARAMS_1 = {"temperature": 0.1}
_JUDGE_PARAMS_2 = {"temperature": 0.1}

_RUBRIC_TEMPLATE = """\
Evaluate the following explanation for a legal contract discrepancy.
Score each dimension from 0 (completely absent/wrong) to 5 (excellent):

1. Accuracy: Does the explanation correctly identify the type and nature of the discrepancy?
2. Completeness: Does it cover all aspects of the discrepancy without missing key elements?
3. Clarity: Is it clearly written and unambiguous?
4. Legal Reasoning: Does it correctly apply relevant legal principles or contractual norms?

Also provide a binary flag:
- adequate (true/false): Is this explanation adequate for a legal audit?

Respond in JSON:
{{"accuracy": <0-5>, "completeness": <0-5>, "clarity": <0-5>, "legal_reasoning": <0-5>, "adequate": <bool>}}

Contract discrepancy context:
Perturbation type: {perturb_type}
Dimension: {dimension}

Predicted explanation:
{pred_explanation}

Reference explanation (ground truth):
{gt_explanation}"""


@dataclass
class ExplanationScore:
    accuracy: float         # 0-5
    completeness: float     # 0-5
    clarity: float          # 0-5
    legal_reasoning: float  # 0-5
    adequate: float         # 0.0 or 1.0 (averaged across judges)
    judge1_raw: dict
    judge2_raw: dict


def _build_prompt(
    pred_explanation: str,
    gt_explanation: str,
    perturb_type: str,
    dimension: str,
) -> str:
    return _RUBRIC_TEMPLATE.format(
        perturb_type=perturb_type,
        dimension=dimension,
        pred_explanation=pred_explanation,
        gt_explanation=gt_explanation,
    )


def _parse_judge_response(raw: str) -> dict:
    return parse_json_response(raw)


async def score_explanation(
    pred_explanation: str,
    gt_explanation: str,
    perturb_type: str,
    dimension: str,
) -> ExplanationScore:
    """Call both judges concurrently, average their scores."""
    prompt = _build_prompt(pred_explanation, gt_explanation, perturb_type, dimension)

    raw1_text, raw2_text = await asyncio.gather(
        generate(prompt, _JUDGE1_ALIAS, _JUDGE_PARAMS_1),
        generate(prompt, _JUDGE2_ALIAS, _JUDGE_PARAMS_2),
    )

    j1 = _parse_judge_response(raw1_text)
    j2 = _parse_judge_response(raw2_text)

    def _avg(key: str) -> float:
        return (float(j1[key]) + float(j2[key])) / 2.0

    def _avg_bool(key: str) -> float:
        v1 = 1.0 if j1[key] else 0.0
        v2 = 1.0 if j2[key] else 0.0
        return (v1 + v2) / 2.0

    return ExplanationScore(
        accuracy=_avg("accuracy"),
        completeness=_avg("completeness"),
        clarity=_avg("clarity"),
        legal_reasoning=_avg("legal_reasoning"),
        adequate=_avg_bool("adequate"),
        judge1_raw=j1,
        judge2_raw=j2,
    )


def score_explanation_sync(
    pred_explanation: str,
    gt_explanation: str,
    perturb_type: str,
    dimension: str,
) -> ExplanationScore:
    """Sync wrapper around score_explanation."""
    return asyncio.run(
        score_explanation(pred_explanation, gt_explanation, perturb_type, dimension)
    )
