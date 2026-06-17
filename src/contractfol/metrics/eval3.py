"""Eval_3 location_alignment metrics: ROUGE-1/2/L, METEOR, BERTScore.

Paper: Choudhury et al., EACL 2026.
Packages: rouge-score 0.1.2, nltk 3.8.1, bert-score 0.3.13.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LocationAlignmentMetrics:
    rouge1: float
    rouge2: float
    rougeL: float
    meteor: float
    n: int          # positive instances evaluated


def _ensure_nltk_resources() -> None:
    import nltk
    for resource in ("punkt", "punkt_tab", "wordnet"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)


def _rouge(prediction: str, reference: str) -> dict[str, float]:
    from rouge_score import rouge_scorer as _rs
    scorer = _rs.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    s = scorer.score(reference, prediction)
    return {"rouge1": s["rouge1"].fmeasure, "rouge2": s["rouge2"].fmeasure, "rougeL": s["rougeL"].fmeasure}


def _meteor(prediction: str, reference: str) -> float:
    import nltk
    from nltk.translate.meteor_score import meteor_score as _m
    _ensure_nltk_resources()
    ref_tok = nltk.word_tokenize(reference.lower())
    pred_tok = nltk.word_tokenize(prediction.lower())
    return float(_m([ref_tok], pred_tok))


def location_alignment(
    predictions_by_id: dict[str, list[dict]],
    instances_by_id: dict,
) -> LocationAlignmentMetrics:
    """Compute location_alignment for Eval_3 predictions (positive instances only).

    predictions_by_id: {instance_id: list of span dicts with "text" key}
    instances_by_id:   {instance_id: DiscrepancyInstance}
    """
    rouge1_acc: list[float] = []
    rouge2_acc: list[float] = []
    rougeL_acc: list[float] = []
    meteor_acc: list[float] = []

    for iid, spans in predictions_by_id.items():
        inst = instances_by_id.get(iid)
        if inst is None or not inst.gold_label:
            continue  # skip negatives

        reference = inst.changed_text
        prediction = spans[0].get("text", "") if spans else ""

        if not prediction.strip():
            # Model found nothing → zeros (FN)
            rouge1_acc.append(0.0)
            rouge2_acc.append(0.0)
            rougeL_acc.append(0.0)
            meteor_acc.append(0.0)
            continue

        try:
            r = _rouge(prediction, reference)
            rouge1_acc.append(r["rouge1"])
            rouge2_acc.append(r["rouge2"])
            rougeL_acc.append(r["rougeL"])
        except Exception as exc:
            logger.warning("ROUGE error %s: %s", iid, exc)
            rouge1_acc.extend([0.0, 0.0, 0.0])

        try:
            meteor_acc.append(_meteor(prediction, reference))
        except Exception as exc:
            logger.warning("METEOR error %s: %s", iid, exc)
            meteor_acc.append(0.0)

    n = len(rouge1_acc)
    if n == 0:
        return LocationAlignmentMetrics(rouge1=0.0, rouge2=0.0, rougeL=0.0, meteor=0.0, n=0)

    return LocationAlignmentMetrics(
        rouge1=sum(rouge1_acc) / n,
        rouge2=sum(rouge2_acc) / n,
        rougeL=sum(rougeL_acc) / n,
        meteor=sum(meteor_acc) / len(meteor_acc) if meteor_acc else 0.0,
        n=n,
    )
