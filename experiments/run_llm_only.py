"""
Runner do braço LLM-only do ContractFOL v3.

Fluxo:
  1. Carrega dataset CLAUSE via corpus.ingest
  2. Cria split dev/test estratificado (ou recarrega split existente)
  3. Seleciona instâncias do split escolhido (default: dev)
  4. Executa run_batch_sync para cada combinação (modelo × task × level)
  5. Salva predições em JSONL + JSON de resumo
  6. Imprime tabela de métricas Eval_1 e Eval_2

Uso:
    python experiments/run_llm_only.py \
        --data data/raw/clause/datasets/ \
        --splits data/splits/ \
        --output outputs/llm_only/ \
        --models gpt-4o-mini deepseek \
        --tasks eval1 eval2 \
        --levels l1 l2

Flags úteis:
    --n-per-cell 50       instâncias por célula (perturb_type × dimension)
    --max-concurrent 5    chamadas de API em paralelo
    --split dev           usar split dev (default) ou test (CUIDADO: contaminação)
    --dry-run             mostra configuração e sai sem chamar APIs
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("contractfol.corpus.ingest").setLevel(logging.WARNING)

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))

from contractfol.arms.llm_only import LLMPrediction, run_batch_sync
from contractfol.corpus.ingest import load_instances
from contractfol.corpus.sample import (
    load_splits,
    make_splits,
    save_splits,
    stratified_sample,
)
from contractfol.corpus.schema import DiscrepancyInstance
from contractfol.metrics.eval1_2 import (
    ClassificationMetrics,
    eval1_metrics,
    eval2_metrics,
    per_category_metrics,
)

logger = logging.getLogger("run_llm_only")

SEP = "─" * 80


# ─── helpers ──────────────────────────────────────────────────────────────────


def _fmt(m: ClassificationMetrics) -> str:
    return (
        f"Acc={m.accuracy:.3f}  P={m.precision:.3f}  "
        f"R={m.recall:.3f}  F1={m.f1:.3f}  "
        f"(TP={m.tp} FP={m.fp} FN={m.fn} TN={m.tn})"
    )


def _print_section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ─── split management ─────────────────────────────────────────────────────────


def ensure_splits(
    data_path: Path,
    splits_dir: Path,
    n_per_cell: int,
    test_fraction: float,
    seed: int,
) -> tuple[list[DiscrepancyInstance], list[DiscrepancyInstance]]:
    """Load existing splits or create and save new ones."""
    dev_path = splits_dir / "dev.jsonl"
    test_path = splits_dir / "test.jsonl"

    if dev_path.exists() and test_path.exists():
        logger.info("Loading existing splits from %s", splits_dir)
        dev, test = load_splits(splits_dir)
        logger.info("dev=%d  test=%d", len(dev), len(test))
        return dev, test

    logger.info("No splits found — creating from dataset")
    instances = load_instances(data_path)
    logger.info("Dataset loaded: %d instances", len(instances))

    sampled = stratified_sample(instances, n_per_cell=n_per_cell, seed=seed)
    logger.info("Sampled (n_per_cell=%d): %d instances", n_per_cell, len(sampled))

    dev, test = make_splits(sampled, test_fraction=test_fraction, seed=seed)
    logger.info("Split → dev=%d  test=%d", len(dev), len(test))

    save_splits(dev, test, splits_dir)
    logger.info("Splits saved to %s", splits_dir)

    return dev, test


# ─── result IO ────────────────────────────────────────────────────────────────


def save_predictions(
    predictions: list[LLMPrediction],
    output_dir: Path,
    run_id: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{run_id}_predictions.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for pred in predictions:
            fh.write(pred.model_dump_json() + "\n")
    logger.info("Saved %d predictions → %s", len(predictions), out_path)
    return out_path


def save_summary(summary: dict, output_dir: Path, run_id: str) -> Path:
    out_path = output_dir / f"{run_id}_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    logger.info("Saved summary → %s", out_path)
    return out_path


# ─── metrics computation and display ─────────────────────────────────────────


def _group_predictions(
    predictions: list[LLMPrediction],
) -> dict[tuple[str, str, str], list[LLMPrediction]]:
    """Group predictions by (model_alias, eval_task, prompt_level)."""
    groups: dict[tuple[str, str, str], list[LLMPrediction]] = defaultdict(list)
    for p in predictions:
        groups[(p.model_alias, p.eval_task, p.prompt_level)].append(p)
    return dict(groups)


def compute_and_print_metrics(
    predictions: list[LLMPrediction],
    instances_by_id: dict[str, DiscrepancyInstance],
) -> dict:
    """Compute Eval_1/Eval_2 metrics, print table, return serialisable dict."""
    groups = _group_predictions(predictions)
    summary: dict = {}

    _print_section("MÉTRICAS EVAL_1 — Detecção binária de defeitos")
    print(f"  {'Modelo':<22}  {'Task':<6}  {'Lvl':<4}  {'N':>5}  {''}")
    print("  " + "─" * 76)

    for (model, task, level), preds in sorted(groups.items()):
        gold = [instances_by_id[p.instance_id].gold_label for p in preds]
        pred_answers = [p.answer for p in preds]

        m = eval1_metrics(pred_answers, gold)
        key = f"{model}__{task}__{level}"
        summary[key] = {
            "n": m.n, "accuracy": m.accuracy, "precision": m.precision,
            "recall": m.recall, "f1": m.f1,
            "tp": m.tp, "fp": m.fp, "fn": m.fn, "tn": m.tn,
        }
        print(f"  {model:<22}  {task:<6}  {level:<4}  {m.n:>5}  {_fmt(m)}")

    _print_section("MÉTRICAS EVAL_2 — Classificação de dimensão (in_text / legal)")

    for (model, task, level), preds in sorted(groups.items()):
        if task != "eval2":
            continue
        gold_dims = [instances_by_id[p.instance_id].dimension for p in preds]
        pred_dims = [p.dimension for p in preds]

        m2 = eval2_metrics(pred_dims, gold_dims)
        print(f"\n  {model}  {task}_{level}  (n={len(preds)})")
        for cls in ("in_text", "legal", "macro"):
            print(f"    {cls:<10} {_fmt(m2[cls])}")

    _print_section("MÉTRICAS EVAL_1 POR CATEGORIA (modelo com maior F1 no geral)")

    best_key = max(
        [(k, v) for k, v in summary.items() if "__eval1__" in k],
        key=lambda kv: kv[1]["f1"],
        default=(None, None),
    )
    if best_key[0]:
        model, task, level = best_key[0].split("__")
        preds = groups[(model, task, level)]
        gold = [instances_by_id[p.instance_id].gold_label for p in preds]
        pred_answers = [p.answer for p in preds]
        cats = [
            f"{instances_by_id[p.instance_id].perturb_type}|"
            f"{instances_by_id[p.instance_id].dimension}"
            for p in preds
        ]
        cat_m = per_category_metrics(pred_answers, gold, cats)
        print(f"\n  Melhor configuração: {model}  {task}_{level}\n")
        print(f"  {'Categoria':<36}  {'N':>5}  {''}")
        print("  " + "─" * 72)
        for cat in sorted(cat_m):
            m = cat_m[cat]
            print(f"  {cat:<36}  {m.n:>5}  {_fmt(m)}")

    return summary


# ─── main ─────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Runner do braço LLM-only — ContractFOL v3"
    )
    p.add_argument("--data",    required=True,
                   help="Caminho para data/raw/clause/datasets/")
    p.add_argument("--splits",  default="data/splits/",
                   help="Diretório onde dev.jsonl / test.jsonl serão lidos/gravados")
    p.add_argument("--output",  default="outputs/llm_only/",
                   help="Diretório de saída para predições e resumo")
    p.add_argument("--models",  nargs="+", required=True,
                   help="Aliases de modelo (ex: gpt-4o-mini deepseek)")
    p.add_argument("--tasks",   nargs="+", default=["eval1"],
                   choices=["eval1", "eval2", "eval3"],
                   help="Tarefas de avaliação a executar")
    p.add_argument("--levels",  nargs="+", default=["l1", "l2"],
                   choices=["l1", "l2"],
                   help="Níveis de prompt")
    p.add_argument("--split",   default="dev", choices=["dev", "test"],
                   help="Qual split usar (default: dev — nunca use test antes de congelar)")
    p.add_argument("--n-per-cell",     type=int, default=50,
                   help="Instâncias por célula no split estratificado")
    p.add_argument("--test-fraction",  type=float, default=0.3,
                   help="Fração do split reservada para test")
    p.add_argument("--seed",           type=int, default=42)
    p.add_argument("--max-concurrent", type=int, default=5,
                   help="Chamadas de API em paralelo")
    p.add_argument("--dry-run", action="store_true",
                   help="Mostra configuração e sai sem chamar APIs")
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.split == "test":
        print(
            "\n!!! AVISO: você está usando o split TEST.\n"
            "!!! Use apenas após congelar o sistema completo.\n"
            "!!! Para desenvolvimento, use --split dev.\n",
            file=sys.stderr,
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    data_path = Path(args.data)
    splits_dir = Path(args.splits)
    output_dir = Path(args.output)

    _print_section("CONFIGURAÇÃO")
    print(f"  run_id          : {run_id}")
    print(f"  data            : {data_path}")
    print(f"  splits          : {splits_dir}")
    print(f"  output          : {output_dir}")
    print(f"  split           : {args.split}")
    print(f"  models          : {args.models}")
    print(f"  tasks           : {args.tasks}")
    print(f"  levels          : {args.levels}")
    print(f"  n_per_cell      : {args.n_per_cell}")
    print(f"  max_concurrent  : {args.max_concurrent}")
    total_calls = (
        args.n_per_cell * 10 * len(args.models) * len(args.tasks) * len(args.levels)
    )
    print(f"  ~chamadas API   : ≤{total_calls:,}")

    if args.dry_run:
        print("\n  [dry-run] Saindo sem chamar APIs.")
        return

    # 1. Splits
    dev, test = ensure_splits(
        data_path, splits_dir, args.n_per_cell, args.test_fraction, args.seed
    )
    instances = dev if args.split == "dev" else test
    logger.info("Usando %s split: %d instâncias", args.split, len(instances))

    instances_by_id = {i.instance_id: i for i in instances}

    # 2. Run
    _print_section(f"EXECUÇÃO — {len(instances)} instâncias × {len(args.models)} modelo(s)")
    predictions = run_batch_sync(
        instances=instances,
        model_aliases=args.models,
        eval_tasks=args.tasks,
        prompt_levels=args.levels,
        max_concurrent=args.max_concurrent,
    )
    logger.info("Predições recebidas: %d", len(predictions))

    # 3. Save raw predictions
    save_predictions(predictions, output_dir, run_id)

    # 4. Metrics
    summary = compute_and_print_metrics(predictions, instances_by_id)

    # 5. Save summary
    full_summary = {
        "run_id": run_id,
        "config": {
            "data": str(data_path),
            "split": args.split,
            "models": args.models,
            "tasks": args.tasks,
            "levels": args.levels,
            "n_per_cell": args.n_per_cell,
            "seed": args.seed,
            "n_instances": len(instances),
            "n_predictions": len(predictions),
        },
        "metrics": summary,
    }
    save_summary(full_summary, output_dir, run_id)

    _print_section("CONCLUÍDO")
    print(f"  Predições : {output_dir}/{run_id}_predictions.jsonl")
    print(f"  Resumo    : {output_dir}/{run_id}_summary.json\n")


if __name__ == "__main__":
    main()
