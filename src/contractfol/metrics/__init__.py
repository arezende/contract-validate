"""ContractFOL metrics package — Eval_1, Eval_2, location alignment, explanation scoring, law match."""

from .eval1_2 import ClassificationMetrics, eval1_metrics, eval2_metrics, per_category_metrics
from .explanation import ExplanationScore, score_explanation, score_explanation_sync
from .law_match import law_match, law_match_accuracy, law_match_batch
from .location import LocationMetrics, location_alignment

__all__ = [
    # eval1_2
    "ClassificationMetrics",
    "eval1_metrics",
    "eval2_metrics",
    "per_category_metrics",
    # location
    "LocationMetrics",
    "location_alignment",
    # explanation
    "ExplanationScore",
    "score_explanation",
    "score_explanation_sync",
    # law_match
    "law_match",
    "law_match_batch",
    "law_match_accuracy",
]
