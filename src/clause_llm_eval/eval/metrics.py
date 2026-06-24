from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from clause_llm_eval.io import read_jsonl, write_json


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def binary_metrics_rows(rows: list[dict]) -> dict[str, Any]:
    valid = [r for r in rows if r.get("prediction") in {0, 1} and r.get("label") in {0, 1}]

    tp = sum(1 for r in valid if r["label"] == 1 and r["prediction"] == 1)
    tn = sum(1 for r in valid if r["label"] == 0 and r["prediction"] == 0)
    fp = sum(1 for r in valid if r["label"] == 0 and r["prediction"] == 1)
    fn = sum(1 for r in valid if r["label"] == 1 and r["prediction"] == 0)

    total = tp + tn + fp + fn
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    specificity = safe_div(tn, tn + fp)
    f1 = safe_div(2 * precision * recall, precision + recall)

    return {
        "n_total": len(rows),
        "n_valid": len(valid),
        "parse_error_rate": safe_div(len(rows) - len(valid), len(rows)),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": safe_div(tp + tn, total),
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "false_positive_rate": safe_div(fp, fp + tn),
        "false_negative_rate": safe_div(fn, fn + tp),
    }


def multiclass_metrics_rows(rows: list[dict], labels: list[str]) -> dict[str, Any]:
    valid = [
        r
        for r in rows
        if isinstance(r.get("prediction"), str)
        and isinstance(r.get("label"), str)
        and r["prediction"] in labels
        and r["label"] in labels
    ]

    confusion: dict[str, dict[str, int]] = {y: {p: 0 for p in labels} for y in labels}

    for r in valid:
        confusion[r["label"]][r["prediction"]] += 1

    per_class = {}
    f1s = []
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[y][label] for y in labels if y != label)
        fn = sum(confusion[label][p] for p in labels if p != label)

        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)

        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(confusion[label].values()),
        }
        f1s.append(f1)

    correct = sum(1 for r in valid if r.get("label") == r.get("prediction"))

    return {
        "n_total": len(rows),
        "n_valid": len(valid),
        "parse_error_rate": safe_div(len(rows) - len(valid), len(rows)),
        "accuracy": safe_div(correct, len(valid)),
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0.0,
        "per_class": per_class,
        "confusion": confusion,
    }


def normalize_text(text: Any) -> str:
    text = "" if text is None else str(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_f1(a: str, b: str) -> float:
    left = normalize_text(a).split()
    right = normalize_text(b).split()
    if not left or not right:
        return 0.0

    counts: dict[str, int] = defaultdict(int)
    for token in right:
        counts[token] += 1

    overlap = 0
    for token in left:
        if counts[token] > 0:
            overlap += 1
            counts[token] -= 1

    precision = safe_div(overlap, len(left))
    recall = safe_div(overlap, len(right))
    return safe_div(2 * precision * recall, precision + recall)


def substring_match(a: str, b: str) -> bool:
    left = normalize_text(a)
    right = normalize_text(b)
    return bool(left and right and (left in right or right in left))


def eval3_gold_spans(label: Any) -> list[str]:
    if not isinstance(label, dict):
        return []

    candidates = [
        label.get("contradicted_text"),
        label.get("location"),
        label.get("contradicted_location"),
    ]
    return [str(c) for c in candidates if c]


def eval3_pred_spans(prediction: Any) -> list[dict]:
    if not isinstance(prediction, dict):
        return []
    spans = prediction.get("spans")
    if not isinstance(spans, list):
        return []
    return [s for s in spans if isinstance(s, dict)]


def best_span_token_f1(pred_spans: list[dict], gold_spans: list[str]) -> float:
    values = []
    for pred in pred_spans:
        pred_text = str(pred.get("text", ""))
        values.extend(token_f1(pred_text, gold) for gold in gold_spans)
    return max(values) if values else 0.0


def has_span_substring_match(pred_spans: list[dict], gold_spans: list[str]) -> bool:
    for pred in pred_spans:
        pred_text = str(pred.get("text", ""))
        if any(substring_match(pred_text, gold) for gold in gold_spans):
            return True
    return False


def law_matches(prediction: Any, gold_citation: Any) -> bool:
    gold = normalize_text(gold_citation)
    if not gold or not isinstance(prediction, dict):
        return False

    candidates = [prediction.get("law_citation"), prediction.get("law")]
    for span in eval3_pred_spans(prediction):
        candidates.extend([span.get("law_citation"), span.get("law")])

    return any(substring_match(str(candidate), gold) for candidate in candidates if candidate)


def eval3_metrics_rows(rows: list[dict]) -> dict[str, Any]:
    valid = [r for r in rows if isinstance(r.get("prediction"), dict)]
    rows_with_gold_span = [r for r in valid if eval3_gold_spans(r.get("label"))]
    rows_with_gold_law = [
        r for r in valid if isinstance(r.get("label"), dict) and r["label"].get("law_citation")
    ]

    non_empty_span_rows = [r for r in valid if eval3_pred_spans(r.get("prediction"))]
    explanation_rows = [
        r
        for r in valid
        if any(normalize_text(s.get("explanation")) for s in eval3_pred_spans(r.get("prediction")))
    ]

    dimension_rows = [
        r for r in valid if isinstance(r.get("label"), dict) and r["label"].get("dimension")
    ]
    dimension_correct = sum(
        1 for r in dimension_rows if r["prediction"].get("dimension") == r["label"].get("dimension")
    )

    has_discrepancy_correct = sum(
        1 for r in valid if bool(r["prediction"].get("has_discrepancy")) is True
    )

    substring_hits = sum(
        1
        for r in rows_with_gold_span
        if has_span_substring_match(
            eval3_pred_spans(r.get("prediction")),
            eval3_gold_spans(r.get("label")),
        )
    )
    token_f1_values = [
        best_span_token_f1(eval3_pred_spans(r.get("prediction")), eval3_gold_spans(r.get("label")))
        for r in rows_with_gold_span
    ]
    law_hits = sum(
        1
        for r in rows_with_gold_law
        if law_matches(r.get("prediction"), r["label"].get("law_citation"))
    )

    return {
        "n_total": len(rows),
        "n_valid": len(valid),
        "parse_error_rate": safe_div(len(rows) - len(valid), len(rows)),
        "has_discrepancy_accuracy": safe_div(has_discrepancy_correct, len(valid)),
        "dimension_accuracy": safe_div(dimension_correct, len(dimension_rows)),
        "span_miss_rate": safe_div(len(valid) - len(non_empty_span_rows), len(valid)),
        "explanation_present_rate": safe_div(len(explanation_rows), len(valid)),
        "n_with_gold_span": len(rows_with_gold_span),
        "span_substring_match_rate": safe_div(substring_hits, len(rows_with_gold_span)),
        "span_token_f1": sum(token_f1_values) / len(token_f1_values) if token_f1_values else 0.0,
        "n_with_gold_law": len(rows_with_gold_law),
        "law_match_rate": safe_div(law_hits, len(rows_with_gold_law)),
    }


def metrics_by_cell(rows: list[dict], task: str) -> dict[str, Any]:
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cell = f"{r['perturb_type']}::{r['dimension']}"
        by_cell[cell].append(r)

    out = {}
    for cell, items in sorted(by_cell.items()):
        if task == "eval1":
            out[cell] = binary_metrics_rows(items)
        elif task == "eval2":
            out[cell] = multiclass_metrics_rows(items, labels=["in_text", "legal", "none"])
        elif task == "eval3":
            out[cell] = eval3_metrics_rows(items)
    return out


def compute_metrics(input_jsonl: str, task: str, output_json: str) -> dict[str, Any]:
    rows = read_jsonl(input_jsonl)

    if task == "eval1":
        overall = binary_metrics_rows(rows)
    elif task == "eval2":
        overall = multiclass_metrics_rows(rows, labels=["in_text", "legal", "none"])
    elif task == "eval3":
        overall = eval3_metrics_rows(rows)
    else:
        raise NotImplementedError("Unknown task.")

    report = {
        "task": task,
        "overall": overall,
        "by_cell": metrics_by_cell(rows, task),
    }

    write_json(report, output_json)
    return report
