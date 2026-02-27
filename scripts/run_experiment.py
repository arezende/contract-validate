#!/usr/bin/env python3
"""
Script para executar experimento de avaliação do ContractFOL.

Conforme design experimental da Seção 6.1 da dissertação:
- 50 contratos selecionados aleatoriamente
- 30 com inconsistências artificiais injetadas
- Total de ~2.250 cláusulas e 87 inconsistências conhecidas

Uso:
    python scripts/run_experiment.py
    python scripts/run_experiment.py --openai-key $OPENAI_API_KEY
    python scripts/run_experiment.py --methods contractfol baseline
"""

import argparse
import os
import sys

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from contractfol.evaluation.experiment import ExperimentConfig, ExperimentRunner


def main():
    parser = argparse.ArgumentParser(
        description="Executa experimento de avaliação do ContractFOL"
    )
    parser.add_argument(
        "--openai-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key",
    )
    parser.add_argument(
        "--anthropic-key",
        type=str,
        default=os.environ.get("ANTHROPIC_API_KEY"),
        help="Anthropic API key",
    )
    parser.add_argument(
        "--google-key",
        type=str,
        default=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
        help="Google/Gemini API key",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="openai",
        choices=["openai", "anthropic", "gemini"],
        help="Provedor LLM para o ContractFOL (default: openai)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="Modelo LLM para o ContractFOL (default: depende do provedor)",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        default=["contractfol", "baseline"],
        help="Métodos a avaliar (contractfol, gpt4_cot, claude_cot, baseline)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Número de execuções para média",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso",
    )
    parser.add_argument(
        "--contracts-dir",
        type=str,
        default="data/contracts",
        help="Diretório com contratos",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/results",
        help="Diretório para salvar resultados",
    )

    args = parser.parse_args()

    # Resolver modelo padrão por provedor quando não especificado
    provider_default_models = {
        "openai": "gpt-4",
        "anthropic": "claude-3-opus-20240229",
        "gemini": "gemini-1.5-pro",
    }
    llm_model = args.llm_model or provider_default_models[args.llm_provider]

    # Configurar experimento
    config = ExperimentConfig(
        openai_api_key=args.openai_key,
        anthropic_api_key=args.anthropic_key,
        google_api_key=args.google_key,
        llm_provider=args.llm_provider,
        llm_model=llm_model,
        methods=args.methods,
        num_runs=args.runs,
        verbose=not args.quiet,
        contracts_dir=args.contracts_dir,
        output_dir=args.output_dir,
    )

    # Executar
    print("\n" + "=" * 60)
    print("ContractFOL - Experimento de Avaliação")
    print("Dissertação: Validação Automatizada de Contratos")
    print("Autor: Anderson Rezende - COPPE/UFRJ")
    print("=" * 60)

    if not args.openai_key and "gpt4_cot" in args.methods:
        print("\nAviso: OpenAI API key não configurada. GPT-4 CoT não será executado.")
        config.methods = [m for m in config.methods if m != "gpt4_cot"]

    if not args.anthropic_key and "claude_cot" in args.methods:
        print("\nAviso: Anthropic API key não configurada. Claude CoT não será executado.")
        config.methods = [m for m in config.methods if m != "claude_cot"]

    if not args.google_key and "gemini_cot" in args.methods:
        print("\nAviso: Google/Gemini API key não configurada. Gemini CoT não será executado.")
        config.methods = [m for m in config.methods if m != "gemini_cot"]

    runner = ExperimentRunner(config)
    results = runner.run_all()
    runner.print_comparison_table()

    print("\n[Experimento concluído]")


if __name__ == "__main__":
    main()
