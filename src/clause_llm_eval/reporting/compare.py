from __future__ import annotations

from clause_llm_eval.io import read_json, write_json


def compare_with_author_metric(
    bootstrap_report_json: str,
    metric: str,
    author_value: float,
    output_json: str,
    tolerance: float = 0.05,
) -> dict:
    report = read_json(bootstrap_report_json)
    boot = report["bootstrap"][metric]

    low = boot["ci95_low"]
    high = boot["ci95_high"]
    mean = boot["mean"]

    inside_ci = low <= author_value <= high
    within_tolerance = abs(mean - author_value) <= tolerance

    result = {
        "metric": metric,
        "author_value": author_value,
        "sample_bootstrap_mean": mean,
        "ci95_low": low,
        "ci95_high": high,
        "tolerance": tolerance,
        "inside_ci95": inside_ci,
        "within_absolute_tolerance": within_tolerance,
        "compatible": inside_ci or within_tolerance,
    }

    write_json(result, output_json)
    return result
