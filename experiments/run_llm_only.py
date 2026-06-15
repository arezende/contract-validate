#!/usr/bin/env python3
"""LLM-only evaluation arm — Eval_1, Eval_2, Eval_3.

Replicates the CLAUSE paper protocol (Choudhury et al., EACL 2026, arXiv:2511.00340).

Config priority (low → high):
  hard defaults → experiment.yaml → env vars → CLI flags

Key env vars:
  CONTRACTFOL_API_KEY   generic API key (fallback for any provider)
  CONTRACTFOL_LLM       override models list  (e.g. "deepseek")
  CONTRACTFOL_MODEL     override model_id inside provider (e.g. "deepseek-chat")
  CONTRACTFOL_TEMPERATURE  override temperature
  CONTRACTFOL_MAX_TOKENS   override max_tokens

Usage:
  python experiments/run_llm_only.py                   # uses experiment.yaml
  python experiments/run_llm_only.py --tasks eval1 eval2 --models deepseek
  python experiments/run_llm_only.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure src/ is importable when run as a script
_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

import yaml

from contractfol.arms.llm_only import LLMPrediction, run_batch_sync
from contractfol.corpus.ingest import load_instances
from contractfol.corpus.sample import load_splits, make_splits, save_splits, stratified_sample
from contractfol.corpus.schema import DiscrepancyInstance
from contractfol.metrics.eval1_2 import eval1_metrics, eval2_metrics, ClassificationMetrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_llm_only")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "src" / "contractfol" / "config" / "experiment.yaml"

_DEFAULTS: dict = {
    "data":           "data/raw/clause/datasets/",
    "splits":         "data/splits/",
    "output":         "outputs/llm_only/",
    "n_per_cell":     50,
    "test_fraction":  0.30,
    "seed":           42,
    "models":         ["deepseek"],
    "tasks":          ["eval1", "eval2"],
    "levels":         ["l1", "l2"],
    "max_concurrent": 5,
    "split":          "dev",
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        logger.warning("Config not found: %s — using defaults", path)
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _env_overrides() -> dict:
    overrides: dict = {}
    if (v := os.getenv("CONTRACTFOL_LLM")):
        overrides["models"] = [v]
    return overrides


def _merge(cfg: dict, args: argparse.Namespace) -> argparse.Namespace:
    resolved = dict(_DEFAULTS)
    for k, v in cfg.items():
        resolved[k] = v
    for k, v in _env_overrides().items():
        resolved[k] = v
    for k in list(resolved):
        cli_val = getattr(args, k, None)
        if cli_val is not None:
            resolved[k] = cli_val
    for k, v in resolved.items():
        setattr(args, k, v)
    return args


# ---------------------------------------------------------------------------
# Split management
# ---------------------------------------------------------------------------


def ensure_splits(
    args: argparse.Namespace,
) -> tuple[list[DiscrepancyInstance], list[DiscrepancyInstance]]:
    splits_path = Path(args.splits)
    dev_file = splits_path / "dev.jsonl"
    test_file = splits_path / "test.jsonl"

    if dev_file.exists() and test_file.exists():
        logger.info("Loading existing splits from %s", splits_path)
        return load_splits(splits_path)

    logger.info("No splits found — generating from %s", args.data)
    instances = load_instances(args.data)
    if not instances:
        raise SystemExit("No instances loaded. Check --data path.")

    sampled = stratified_sample(instances, n_per_cell=args.n_per_cell, seed=args.seed)
    dev, test = make_splits(sampled, test_fraction=args.test_fraction, seed=args.seed)
    save_splits(dev, test, splits_path)
    logger.info("Splits saved — dev=%d, test=%d", len(dev), len(test))
    return dev, test


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

_MODEL_TO_KEY_ENV: dict[str, list[str]] = {
    "deepseek":          ["DEEPSEEK_API_KEY", "CONTRACTFOL_API_KEY"],
    "deepseek-reasoner": ["DEEPSEEK_API_KEY", "CONTRACTFOL_API_KEY"],
    "gpt-4o":            ["OPENAI_API_KEY",   "CONTRACTFOL_API_KEY"],
    "gpt-4o-mini":       ["OPENAI_API_KEY",   "CONTRACTFOL_API_KEY"],
    "gemini-2.0-flash":  ["GOOGLE_API_KEY",   "CONTRACTFOL_API_KEY"],
    "gemini-2.5-flash":  ["GOOGLE_API_KEY",   "CONTRACTFOL_API_KEY"],
    "llama-3.3-70b":     ["GROQ_API_KEY",     "CONTRACTFOL_API_KEY"],
    "qwen":              ["DASHSCOPE_API_KEY", "CONTRACTFOL_API_KEY"],
    "kimi":              ["MOONSHOT_API_KEY",  "CONTRACTFOL_API_KEY"],
}


def _validate_api_keys(models: list[str]) -> None:
    missing = []
    for model in models:
        envs = _MODEL_TO_KEY_ENV.get(model, ["CONTRACTFOL_API_KEY"])
        if not any(os.getenv(e) for e in envs):
            missing.append(f"  {model}: needs one of {envs}")
    if missing:
        logger.error("Missing API keys for requested models:\n%s", "\n".join(missing))
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Metrics display
# ---------------------------------------------------------------------------


def _row(label: str, m: ClassificationMetrics) -> str:
    return (
        f"  {label:<20} "
        f"N={m.n:>4}  "
        f"P={m.precision:.3f}  R={m.recall:.3f}  F1={m.f1:.3f}  "
        f"Acc={m.accuracy:.3f}  "
        f"TP={m.tp} FP={m.fp} FN={m.fn} TN={m.tn}"
    )


def _print_eval1(model: str, level: str, m: ClassificationMetrics) -> None:
    print(f"\n[Eval_1] model={model} level={level}")
    print(_row("detection", m))


def _print_eval2(model: str, level: str, dim_metrics: dict[str, ClassificationMetrics]) -> None:
    print(f"\n[Eval_2] model={model} level={level}")
    for dim in ("in_text", "legal", "macro"):
        if dim in dim_metrics:
            print(_row(dim, dim_metrics[dim]))


def compute_and_save_metrics(
    predictions: list[LLMPrediction],
    instances: list[DiscrepancyInstance],
    args: argparse.Namespace,
) -> dict:
    inst_map = {inst.instance_id: inst for inst in instances}
    results: dict = {}

    for model in args.models:
        for task in args.tasks:
            model_task_preds = [
                p for p in predictions
                if p.model_alias == model and p.eval_task == task
            ]
            levels = sorted({p.prompt_level for p in model_task_preds})

            for level in levels:
                level_preds = [p for p in model_task_preds if p.prompt_level == level]
                if not level_preds:
                    continue

                key = f"{model}__{task}__{level}"

                if task == "eval1":
                    pred_answers = [p.answer for p in level_preds]
                    # All CLAUSE instances are positive (gold_label=True)
                    gold_labels = [True] * len(level_preds)
                    m = eval1_metrics(pred_answers, gold_labels)
                    results[key] = m.__dict__
                    _print_eval1(model, level, m)

                elif task == "eval2":
                    pred_dims = [p.dimension for p in level_preds]
                    gold_dims = [inst_map[p.instance_id].dimension for p in level_preds]
                    dim_m = eval2_metrics(pred_dims, gold_dims)
                    results[key] = {k: v.__dict__ for k, v in dim_m.items()}
                    _print_eval2(model, level, dim_m)

                elif task == "eval3":
                    # Detection only (span metrics require separate harness)
                    pred_answers = [p.answer for p in level_preds]
                    gold_labels = [True] * len(level_preds)
                    m = eval1_metrics(pred_answers, gold_labels)
                    results[key] = {"detection": m.__dict__}
                    print(f"\n[Eval_3 detection] model={model} level={level}")
                    print(_row("spans found", m))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="LLM-only evaluation arm for ContractFOL v3",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", type=Path, default=_CONFIG_PATH)
    p.add_argument("--data",   type=str,  default=None)
    p.add_argument("--splits", type=str,  default=None)
    p.add_argument("--output", type=str,  default=None)
    p.add_argument("--models", nargs="+", default=None)
    p.add_argument("--tasks",  nargs="+", default=None,
                   help="eval1 | eval2 | eval3 (combinations allowed)")
    p.add_argument("--levels", nargs="+", default=None,
                   help="l1 | l2 (applies to eval3; eval1/eval2 are levelless)")
    p.add_argument("--split",  choices=["dev", "test"], default=None)
    p.add_argument("--n-per-cell",     type=int,   default=None, dest="n_per_cell")
    p.add_argument("--test-fraction",  type=float, default=None, dest="test_fraction")
    p.add_argument("--seed",           type=int,   default=None)
    p.add_argument("--max-concurrent", type=int,   default=None, dest="max_concurrent")
    p.add_argument("--dry-run", action="store_true",
                   help="Print resolved config and exit without calling any API")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    cfg = _load_yaml(args.config)
    args = _merge(cfg, args)

    print("\n=== ContractFOL v3 — LLM-only evaluation ===")
    print(f"  models         : {args.models}")
    print(f"  tasks          : {args.tasks}")
    print(f"  levels         : {args.levels}  (eval1/eval2 are levelless)")
    print(f"  split          : {args.split}")
    print(f"  n_per_cell     : {args.n_per_cell}")
    print(f"  max_concurrent : {args.max_concurrent}")
    print(f"  output         : {args.output}")

    if args.dry_run:
        print("\n[dry-run] Exiting without API calls.")
        return

    _validate_api_keys(args.models)

    dev, test = ensure_splits(args)
    instances = dev if args.split == "dev" else test
    logger.info("Running on %s split: %d instances", args.split, len(instances))

    predictions = run_batch_sync(
        instances=instances,
        model_aliases=args.models,
        eval_tasks=args.tasks,
        prompt_levels=args.levels,
        max_concurrent=args.max_concurrent,
    )
    logger.info("Total predictions: %d", len(predictions))

    print("\n=== Metrics ===")
    results = compute_and_save_metrics(predictions, instances, args)

    # Persist results
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"
    with results_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    logger.info("Results saved to %s", results_path)

    # Persist raw predictions
    preds_path = out_dir / "predictions.jsonl"
    with preds_path.open("w", encoding="utf-8") as fh:
        for pred in predictions:
            fh.write(pred.model_dump_json() + "\n")
    logger.info("Predictions saved to %s", preds_path)


if __name__ == "__main__":
    main()
