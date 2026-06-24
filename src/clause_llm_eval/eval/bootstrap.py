from __future__ import annotations

import random
from collections import defaultdict
from statistics import mean, stdev
from typing import Any

from clause_llm_eval.eval.metrics import binary_metrics_rows, eval3_metrics_rows, multiclass_metrics_rows
from clause_llm_eval.io import read_jsonl, write_json


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "p50": 0.0}
    return {
        "mean": float(mean(values)),
        "std": float(stdev(values)) if len(values) > 1 else 0.0,
        "ci95_low": float(quantile(values, 0.025)),
        "ci95_high": float(quantile(values, 0.975)),
        "p50": float(quantile(values, 0.50)),
    }


def cell_key(row: dict) -> str:
    return f"{row['perturb_type']}::{row['dimension']}"


def bootstrap_predictions(
    input_jsonl: str,
    task: str,
    output_json: str,
    n_bootstrap: int = 5000,
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    rows = read_jsonl(input_jsonl)

    by_unit: dict[str, list[dict]] = defaultdict(list)

    if task == "eval1":
        for row in rows:
            by_unit[row["instance_id"]].append(row)
    elif task in {"eval2", "eval3"}:
        for row in rows:
            by_unit[row["eval_id"]].append(row)
    else:
        raise NotImplementedError("Bootstrap implementado para eval1/eval2/eval3.")

    units = []
    for unit_id, unit_rows in by_unit.items():
        units.append({
            "unit_id": unit_id,
            "cell": cell_key(unit_rows[0]),
            "rows": unit_rows,
        })

    units_by_cell: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        units_by_cell[unit["cell"]].append(unit)

    metrics_per_round: list[dict] = []

    for _ in range(n_bootstrap):
        sample_rows: list[dict] = []

        for _, cell_units in sorted(units_by_cell.items()):
            n_cell = len(cell_units)
            for _ in range(n_cell):
                unit = rng.choice(cell_units)
                sample_rows.extend(unit["rows"])

        if task == "eval1":
            m = binary_metrics_rows(sample_rows)
        elif task == "eval2":
            m = multiclass_metrics_rows(sample_rows, labels=["in_text", "legal", "none"])
        else:
            m = eval3_metrics_rows(sample_rows)

        metrics_per_round.append(m)

    if task == "eval1":
        metric_names = [
            "accuracy",
            "precision",
            "recall",
            "specificity",
            "f1",
            "false_positive_rate",
            "false_negative_rate",
            "parse_error_rate",
        ]
        full = binary_metrics_rows(rows)
    elif task == "eval2":
        metric_names = ["accuracy", "macro_f1", "parse_error_rate"]
        full = multiclass_metrics_rows(rows, labels=["in_text", "legal", "none"])
    else:
        metric_names = [
            "has_discrepancy_accuracy",
            "dimension_accuracy",
            "span_miss_rate",
            "explanation_present_rate",
            "span_substring_match_rate",
            "span_token_f1",
            "law_match_rate",
            "parse_error_rate",
        ]
        full = eval3_metrics_rows(rows)

    summary = {
        "task": task,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "n_rows": len(rows),
        "n_units": len(units),
        "full_sample_metrics": full,
        "bootstrap": {},
    }

    for metric in metric_names:
        values = [float(m.get(metric, 0.0)) for m in metrics_per_round]
        summary["bootstrap"][metric] = summarize(values)

    write_json(summary, output_json)
    return summary
