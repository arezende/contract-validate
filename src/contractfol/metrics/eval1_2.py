"""Eval_1 (binary defect detection) and Eval_2 (dimension classification) metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    n: int   # number of instances
    tp: int
    fp: int
    fn: int
    tn: int


def _safe_div(numerator: float, denominator: float) -> float:
    """Division that returns 0.0 instead of NaN on zero-denominator."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _compute_metrics(tp: int, fp: int, fn: int, tn: int) -> ClassificationMetrics:
    n = tp + fp + fn + tn
    accuracy = _safe_div(tp + tn, n)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return ClassificationMetrics(
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        n=n,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
    )


def eval1_metrics(
    predictions: list[bool],
    gold_labels: list[bool],
) -> ClassificationMetrics:
    """Binary defect detection (Eval_1). Positive class = True (UNSAT = defect)."""
    if len(predictions) != len(gold_labels):
        raise ValueError(
            f"Length mismatch: predictions={len(predictions)}, gold_labels={len(gold_labels)}"
        )

    tp = fp = fn = tn = 0
    for pred, gold in zip(predictions, gold_labels):
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif not pred and gold:
            fn += 1
        else:
            tn += 1

    return _compute_metrics(tp, fp, fn, tn)


def eval2_metrics(
    predictions: list[str | None],
    gold_dimensions: list[str],
) -> dict[str, ClassificationMetrics]:
    """
    Dimension classification (Eval_2) — 3-class: in_text, legal, none (no_contradiction).

    Returns dict with keys "in_text", "legal", "none", "macro", and "overall_accuracy".
    overall_accuracy is the standard multiclass accuracy (matches paper Table 4).
    A prediction of None counts as "none".
    """
    if len(predictions) != len(gold_dimensions):
        raise ValueError(
            f"Length mismatch: predictions={len(predictions)}, gold_dimensions={len(gold_dimensions)}"
        )

    classes = ["in_text", "legal", "none"]
    counts: dict[str, dict[str, int]] = {
        c: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for c in classes
    }

    n_correct = 0
    for pred, gold in zip(predictions, gold_dimensions):
        pred_norm = pred if pred in classes else "none"
        if pred_norm == gold:
            n_correct += 1
        for cls in classes:
            pred_positive = pred_norm == cls
            gold_positive = gold == cls
            if pred_positive and gold_positive:
                counts[cls]["tp"] += 1
            elif pred_positive and not gold_positive:
                counts[cls]["fp"] += 1
            elif not pred_positive and gold_positive:
                counts[cls]["fn"] += 1
            else:
                counts[cls]["tn"] += 1

    result: dict[str, ClassificationMetrics] = {}
    for cls in classes:
        c = counts[cls]
        result[cls] = _compute_metrics(c["tp"], c["fp"], c["fn"], c["tn"])

    # Macro average across all 3 classes
    macro_f1 = _safe_div(sum(result[c].f1 for c in classes), len(classes))
    macro_precision = _safe_div(sum(result[c].precision for c in classes), len(classes))
    macro_recall = _safe_div(sum(result[c].recall for c in classes), len(classes))
    macro_accuracy = _safe_div(n_correct, len(predictions))   # true overall accuracy
    macro_n = len(predictions)
    macro_tp = sum(result[c].tp for c in classes)
    macro_fp = sum(result[c].fp for c in classes)
    macro_fn = sum(result[c].fn for c in classes)
    macro_tn = sum(result[c].tn for c in classes)
    result["macro"] = ClassificationMetrics(
        accuracy=macro_accuracy,
        precision=macro_precision,
        recall=macro_recall,
        f1=macro_f1,
        n=macro_n,
        tp=macro_tp,
        fp=macro_fp,
        fn=macro_fn,
        tn=macro_tn,
    )

    return result


def per_category_metrics(
    predictions: list[bool],
    gold_labels: list[bool],
    categories: list[str],
) -> dict[str, ClassificationMetrics]:
    """F1 per (perturb_type × dimension) category string."""
    if len(predictions) != len(gold_labels) or len(predictions) != len(categories):
        raise ValueError("All input lists must have the same length.")

    cat_data: dict[str, dict[str, int]] = {}
    for pred, gold, cat in zip(predictions, gold_labels, categories):
        if cat not in cat_data:
            cat_data[cat] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        if pred and gold:
            cat_data[cat]["tp"] += 1
        elif pred and not gold:
            cat_data[cat]["fp"] += 1
        elif not pred and gold:
            cat_data[cat]["fn"] += 1
        else:
            cat_data[cat]["tn"] += 1

    return {
        cat: _compute_metrics(d["tp"], d["fp"], d["fn"], d["tn"])
        for cat, d in cat_data.items()
    }
