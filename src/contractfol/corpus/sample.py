"""Stratified sampling and frozen dev/test split utilities for ContractFOL.

IMPORTANT: The test split must be frozen after first generation.
Prompt calibration, threshold tuning, and any hyperparameter search
must use ONLY the dev split. Loading test.jsonl during development
is a protocol violation.
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from contractfol.corpus.schema import DiscrepancyInstance

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CellKey = tuple[str, str]  # (perturb_type, dimension)


def _cell_key(inst: DiscrepancyInstance) -> _CellKey:
    return (inst.perturb_type, inst.dimension)


def _group_by_cell(
    instances: list[DiscrepancyInstance],
) -> dict[_CellKey, list[DiscrepancyInstance]]:
    groups: dict[_CellKey, list[DiscrepancyInstance]] = defaultdict(list)
    for inst in instances:
        groups[_cell_key(inst)].append(inst)
    return groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def stratified_sample(
    instances: list[DiscrepancyInstance],
    n_per_cell: int = 50,
    seed: int = 42,
) -> list[DiscrepancyInstance]:
    """Sample n_per_cell instances per (perturb_type × dimension) cell.

    If a cell has fewer than n_per_cell instances, all instances in that cell
    are included.  Uses a fixed seed for reproducibility.

    Parameters
    ----------
    instances:
        Full pool of DiscrepancyInstance objects to sample from.
    n_per_cell:
        Maximum number of instances to draw from each stratification cell.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    list[DiscrepancyInstance]
        Sampled instances (order is deterministic given the same inputs).
    """
    rng = random.Random(seed)
    groups = _group_by_cell(instances)

    result: list[DiscrepancyInstance] = []
    for key in sorted(groups):
        cell = groups[key]
        if len(cell) <= n_per_cell:
            result.extend(cell)
        else:
            result.extend(rng.sample(cell, n_per_cell))

    return result


def create_negatives(positives: list[DiscrepancyInstance]) -> list[DiscrepancyInstance]:
    """Create one negative (unperturbed) instance for each positive.

    Protocol (CLAUSE paper §3):
      Eval_1 — model receives (original_text, changed_text). For negatives,
               changed_text == original_text, so the model should answer "No".
      Eval_2 — model receives only changed_text. For negatives this is the
               original unperturbed contract; the gold class is "no_contradiction".

    dimension is inherited from the source positive for per-category bucketing
    (matches Table 3 of the paper where each category mixes pos+neg). gold_label=False
    is the sole indicator that this is a negative.
    """
    return [
        DiscrepancyInstance(
            instance_id=f"{inst.instance_id}_neg",
            source_dataset=inst.source_dataset,
            perturb_type=inst.perturb_type,
            dimension=inst.dimension,          # inherited — for category tracking only
            original_text=inst.original_text,
            changed_text=inst.original_text,   # no modification → identical to original
            explanation="",
            gold_label=False,
        )
        for inst in positives
    ]


def make_splits(
    instances: list[DiscrepancyInstance],
    test_fraction: float = 0.3,
    seed: int = 42,
) -> tuple[list[DiscrepancyInstance], list[DiscrepancyInstance]]:
    """Split instances into dev and test sets, stratified by (perturb_type × dimension).

    The split is deterministic given the same seed and input list order.

    Parameters
    ----------
    instances:
        Pool of instances to split (typically the output of
        :func:`stratified_sample`).
    test_fraction:
        Fraction of each cell to assign to the test set.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    (dev, test)
        Two lists of DiscrepancyInstance; dev + test covers all inputs.
    """
    if not 0.0 < test_fraction < 1.0:
        raise ValueError(f"test_fraction must be in (0, 1), got {test_fraction}")

    rng = random.Random(seed)
    groups = _group_by_cell(instances)

    dev: list[DiscrepancyInstance] = []
    test: list[DiscrepancyInstance] = []

    for key in sorted(groups):
        cell = list(groups[key])
        rng.shuffle(cell)
        n_test = max(1, round(len(cell) * test_fraction)) if len(cell) > 1 else 0
        test.extend(cell[:n_test])
        dev.extend(cell[n_test:])

    return dev, test


def save_splits(
    dev: list[DiscrepancyInstance],
    test: list[DiscrepancyInstance],
    output_dir: str | Path,
) -> None:
    """Save dev.jsonl and test.jsonl to output_dir.

    Each file contains one JSON object per line (JSONL format).
    The output directory is created if it does not already exist.

    Parameters
    ----------
    dev:
        Development split instances.
    test:
        Test split instances.
    output_dir:
        Directory path where the files will be written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, split in (("dev", dev), ("test", test)):
        out_path = output_dir / f"{name}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for inst in split:
                fh.write(inst.model_dump_json() + "\n")


def load_splits(
    output_dir: str | Path,
) -> tuple[list[DiscrepancyInstance], list[DiscrepancyInstance]]:
    """Load dev.jsonl and test.jsonl from output_dir.

    Parameters
    ----------
    output_dir:
        Directory containing ``dev.jsonl`` and ``test.jsonl``.

    Returns
    -------
    (dev, test)
        Reconstructed DiscrepancyInstance lists.
    """
    output_dir = Path(output_dir)

    def _read(name: str) -> list[DiscrepancyInstance]:
        path = output_dir / f"{name}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        result = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    result.append(DiscrepancyInstance(**json.loads(line)))
                except Exception as exc:
                    raise ValueError(
                        f"Failed to parse line {lineno} of {path}: {exc}"
                    ) from exc
        return result

    dev = _read("dev")
    test = _read("test")
    return dev, test


def load_test_split_with_warning(
    output_dir: str | Path,
) -> list[DiscrepancyInstance]:
    """Load the test split from output_dir, with a prominent warning.

    *** DO NOT call this function during development. ***

    Loading the test split before finalising your system constitutes a
    protocol violation (test contamination).  Prompt calibration, threshold
    tuning, and any hyperparameter search must use ONLY the dev split.

    Parameters
    ----------
    output_dir:
        Directory containing ``test.jsonl``.

    Returns
    -------
    list[DiscrepancyInstance]
        The frozen test split.
    """
    warning = (
        "\n"
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        "!!  WARNING: You are loading the TEST split.                      !!\n"
        "!!  The test split must be frozen after first generation.         !!\n"
        "!!  Any use of test data for calibration, threshold tuning, or    !!\n"
        "!!  hyperparameter search is a PROTOCOL VIOLATION.                !!\n"
        "!!  Use the DEV split (load_splits()[0]) during development.      !!\n"
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
    )
    print(warning, file=sys.stderr, flush=True)

    output_dir = Path(output_dir)
    path = output_dir / "test.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")

    result = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                result.append(DiscrepancyInstance(**json.loads(line)))
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse line {lineno} of {path}: {exc}"
                ) from exc
    return result
