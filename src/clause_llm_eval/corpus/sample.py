from __future__ import annotations

import random
from collections import defaultdict

from clause_llm_eval.io import read_jsonl, write_jsonl


def cell_key(row: dict) -> str:
    return f"{row['perturb_type']}::{row['dimension']}"


def make_splits(
    input_jsonl: str,
    dev_output: str,
    test_output: str,
    test_fraction: float = 0.30,
    seed: int = 42,
) -> dict:
    rng = random.Random(seed)
    rows = read_jsonl(input_jsonl)

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cell[cell_key(row)].append(row)

    dev: list[dict] = []
    test: list[dict] = []
    report: dict[str, dict] = {}

    for cell, items in sorted(by_cell.items()):
        items = list(items)
        rng.shuffle(items)

        n_test = round(len(items) * test_fraction)
        test_items = items[:n_test]
        dev_items = items[n_test:]

        test.extend(test_items)
        dev.extend(dev_items)

        report[cell] = {
            "total": len(items),
            "dev": len(dev_items),
            "test": len(test_items),
        }

    rng.shuffle(dev)
    rng.shuffle(test)

    write_jsonl(dev, dev_output)
    write_jsonl(test, test_output)

    return {
        "total": len(rows),
        "dev": len(dev),
        "test": len(test),
        "by_cell": report,
    }


def stratified_fraction_sample(
    input_jsonl: str,
    output_jsonl: str,
    fraction: float = 0.10,
    seed: int = 42,
    min_per_cell: int = 1,
) -> dict:
    rng = random.Random(seed)
    rows = read_jsonl(input_jsonl)

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cell[cell_key(row)].append(row)

    sampled: list[dict] = []
    report: dict[str, dict] = {}

    for cell, items in sorted(by_cell.items()):
        items = list(items)
        n_total = len(items)
        n_sample = max(min_per_cell, round(n_total * fraction))
        n_sample = min(n_sample, n_total)

        selected = rng.sample(items, n_sample)
        sampled.extend(selected)

        report[cell] = {
            "total": n_total,
            "sampled": n_sample,
            "fraction": n_sample / n_total if n_total else 0.0,
        }

    rng.shuffle(sampled)
    write_jsonl(sampled, output_jsonl)

    return {
        "input_total": len(rows),
        "sampled_total": len(sampled),
        "fraction_requested": fraction,
        "by_cell": report,
    }
