from clause_llm_eval.eval.bootstrap import bootstrap_predictions
from clause_llm_eval.eval.metrics import eval3_metrics_rows
from clause_llm_eval.io import read_json, write_jsonl


def test_eval3_metrics_span_and_law_match():
    rows = [
        {
            "eval_id": "e1",
            "instance_id": "i1",
            "perturb_type": "omission",
            "dimension": "legal",
            "label": {
                "dimension": "legal",
                "contradicted_text": "Employees must receive overtime pay.",
                "law_citation": "29 U.S.C. 207",
            },
            "prediction": {
                "has_discrepancy": True,
                "dimension": "legal",
                "spans": [
                    {
                        "text": "Employees must receive overtime pay.",
                        "explanation": "The contract conflicts with overtime law.",
                        "law_citation": "29 U.S.C. 207",
                    }
                ],
            },
        }
    ]

    metrics = eval3_metrics_rows(rows)

    assert metrics["has_discrepancy_accuracy"] == 1
    assert metrics["dimension_accuracy"] == 1
    assert metrics["span_miss_rate"] == 0
    assert metrics["span_substring_match_rate"] == 1
    assert metrics["span_token_f1"] == 1
    assert metrics["law_match_rate"] == 1


def test_eval3_bootstrap(tmp_path):
    input_path = tmp_path / "predictions.jsonl"
    output_path = tmp_path / "bootstrap.json"
    write_jsonl(
        [
            {
                "eval_id": "e1",
                "instance_id": "i1",
                "perturb_type": "inconsistency",
                "dimension": "in_text",
                "label": {
                    "dimension": "in_text",
                    "contradicted_text": "Delivery is due in 30 days.",
                },
                "prediction": {
                    "has_discrepancy": True,
                    "dimension": "in_text",
                    "spans": [{"text": "Delivery is due in 30 days.", "explanation": "Conflict"}],
                },
            }
        ],
        input_path,
    )

    report = bootstrap_predictions(str(input_path), "eval3", str(output_path), n_bootstrap=10, seed=42)
    saved = read_json(output_path)

    assert report["bootstrap"]["span_substring_match_rate"]["mean"] == 1
    assert saved["task"] == "eval3"
