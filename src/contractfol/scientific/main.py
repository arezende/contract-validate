"""CLI entrypoint for the scientific ContractFOL pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .pipeline import executar_pipeline
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from contractfol.scientific.pipeline import executar_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="ContractFOL scientific pipeline")
    parser.add_argument("--contrato-a", required=True, type=Path, help="Path to contract A")
    parser.add_argument("--contrato-b", type=Path, default=None, help="Optional path to contract B")
    parser.add_argument(
        "--estrategia",
        default="few_shot",
        choices=["zero_shot", "few_shot", "cot", "composicional"],
        help="Translation strategy",
    )
    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()
    executar_pipeline(args.contrato_a, args.contrato_b, args.estrategia)


if __name__ == "__main__":
    main()
