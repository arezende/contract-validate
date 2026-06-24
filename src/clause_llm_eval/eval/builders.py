from __future__ import annotations

import random

from clause_llm_eval.io import read_jsonl, write_jsonl


def build_eval1(input_jsonl: str, output_jsonl: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    instances = read_jsonl(input_jsonl)

    rows: list[dict] = []

    for item in instances:
        base = {
            "instance_id": item["instance_id"],
            "source_dataset": item["source_dataset"],
            "perturb_type": item["perturb_type"],
            "dimension": item["dimension"],
            "task": "eval1",
        }

        rows.append({
            **base,
            "eval_id": f"{item['instance_id']}__changed",
            "variant": "changed",
            "doc": item["changed_text"],
            "label": 1,
            "gold": "Yes",
        })

        rows.append({
            **base,
            "eval_id": f"{item['instance_id']}__original",
            "variant": "original",
            "doc": item["original_text"],
            "label": 0,
            "gold": "No",
        })

    rng.shuffle(rows)
    write_jsonl(rows, output_jsonl)

    return {
        "instances": len(instances),
        "eval_rows": len(rows),
        "output": output_jsonl,
    }


def build_eval2(input_jsonl: str, output_jsonl: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    instances = read_jsonl(input_jsonl)

    rows: list[dict] = []

    for item in instances:
        rows.append({
            "eval_id": f"{item['instance_id']}__changed",
            "instance_id": item["instance_id"],
            "source_dataset": item["source_dataset"],
            "perturb_type": item["perturb_type"],
            "dimension": item["dimension"],
            "task": "eval2",
            "variant": "changed",
            "doc": item["changed_text"],
            "label": item["dimension"],
            "gold": item["dimension"],
        })

    rng.shuffle(rows)
    write_jsonl(rows, output_jsonl)

    return {
        "instances": len(instances),
        "eval_rows": len(rows),
        "output": output_jsonl,
    }


def build_eval3(input_jsonl: str, output_jsonl: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    instances = read_jsonl(input_jsonl)

    rows: list[dict] = []

    for item in instances:
        rows.append({
            "eval_id": f"{item['instance_id']}__changed",
            "instance_id": item["instance_id"],
            "source_dataset": item["source_dataset"],
            "perturb_type": item["perturb_type"],
            "dimension": item["dimension"],
            "task": "eval3",
            "variant": "changed",
            "doc": item["changed_text"],
            "label": {
                "location": item.get("location"),
                "contradicted_location": item.get("contradicted_location"),
                "contradicted_text": item.get("contradicted_text"),
                "law_citation": item.get("law_citation"),
                "dimension": item.get("dimension"),
                "perturb_type": item.get("perturb_type"),
            },
            "gold": {
                "location": item.get("location"),
                "contradicted_location": item.get("contradicted_location"),
                "contradicted_text": item.get("contradicted_text"),
                "law_citation": item.get("law_citation"),
                "dimension": item.get("dimension"),
                "perturb_type": item.get("perturb_type"),
            },
        })

    rng.shuffle(rows)
    write_jsonl(rows, output_jsonl)

    return {
        "instances": len(instances),
        "eval_rows": len(rows),
        "output": output_jsonl,
    }
