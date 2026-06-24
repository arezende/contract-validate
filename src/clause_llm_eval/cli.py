from __future__ import annotations

import argparse
import json

from clause_llm_eval.corpus.ingest import ingest_to_jsonl
from clause_llm_eval.corpus.sample import make_splits, stratified_fraction_sample
from clause_llm_eval.eval.builders import build_eval1, build_eval2, build_eval3
from clause_llm_eval.eval.bootstrap import bootstrap_predictions
from clause_llm_eval.eval.metrics import compute_metrics
from clause_llm_eval.eval.runner import run_eval
from clause_llm_eval.reporting.compare import compare_with_author_metric


def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clause-eval",
        description="Pipeline de avaliação de LLMs no benchmark CLAUSE.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="Ingerir dataset CLAUSE bruto para JSONL canônico.")
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("make-splits", help="Gerar dev/test estratificados.")
    p.add_argument("--input", required=True)
    p.add_argument("--dev-output", required=True)
    p.add_argument("--test-output", required=True)
    p.add_argument("--test-fraction", type=float, default=0.30)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("sample", help="Criar subamostra estratificada.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--fraction", type=float, default=0.10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-per-cell", type=int, default=1)

    p = sub.add_parser("build-eval1", help="Construir arquivo Eval_1.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("build-eval2", help="Construir arquivo Eval_2.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("build-eval3", help="Construir arquivo Eval_3.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("run", help="Executar LLM sobre arquivo de avaliação.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--task", choices=["eval1", "eval2", "eval3"], required=True)
    p.add_argument("--provider", choices=["mock", "openai", "gemini", "ollama"], required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--sleep-seconds", type=float, default=0.0)

    p = sub.add_parser("metrics", help="Calcular métricas.")
    p.add_argument("--input", required=True)
    p.add_argument("--task", choices=["eval1", "eval2", "eval3"], required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("bootstrap", help="Bootstrap estratificado sobre predições salvas.")
    p.add_argument("--input", required=True)
    p.add_argument("--task", choices=["eval1", "eval2", "eval3"], required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--n-bootstrap", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("compare-author", help="Comparar métrica bootstrap com valor reportado pelos autores.")
    p.add_argument("--bootstrap-report", required=True)
    p.add_argument("--metric", required=True)
    p.add_argument("--author-value", type=float, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--tolerance", type=float, default=0.05)

    args = parser.parse_args()

    if args.command == "ingest":
        ingest_to_jsonl(args.data, args.output)
        print_json({"output": args.output})

    elif args.command == "make-splits":
        print_json(make_splits(
            input_jsonl=args.input,
            dev_output=args.dev_output,
            test_output=args.test_output,
            test_fraction=args.test_fraction,
            seed=args.seed,
        ))

    elif args.command == "sample":
        print_json(stratified_fraction_sample(
            input_jsonl=args.input,
            output_jsonl=args.output,
            fraction=args.fraction,
            seed=args.seed,
            min_per_cell=args.min_per_cell,
        ))

    elif args.command == "build-eval1":
        print_json(build_eval1(args.input, args.output, seed=args.seed))

    elif args.command == "build-eval2":
        print_json(build_eval2(args.input, args.output, seed=args.seed))

    elif args.command == "build-eval3":
        print_json(build_eval3(args.input, args.output, seed=args.seed))

    elif args.command == "run":
        print_json(run_eval(
            input_jsonl=args.input,
            output_jsonl=args.output,
            task=args.task,
            provider_name=args.provider,
            model=args.model,
            temperature=args.temperature,
            limit=args.limit,
            resume=not args.no_resume,
            sleep_seconds=args.sleep_seconds,
        ))

    elif args.command == "metrics":
        print_json(compute_metrics(args.input, args.task, args.output))

    elif args.command == "bootstrap":
        print_json(bootstrap_predictions(
            input_jsonl=args.input,
            task=args.task,
            output_json=args.output,
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        ))

    elif args.command == "compare-author":
        print_json(compare_with_author_metric(
            bootstrap_report_json=args.bootstrap_report,
            metric=args.metric,
            author_value=args.author_value,
            output_json=args.output,
            tolerance=args.tolerance,
        ))


if __name__ == "__main__":
    main()
