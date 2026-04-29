"""ContractFOL V3 — Análise Intra-Contrato Neurossimbólica."""

__version__ = "3.0.0"
__author__ = "Anderson Rezende (COPPE/UFRJ)"

from contractfol.contractfol.core import (
    analisar_contrato,
    compilar_extracao,
    extrair_contrato,
    gerar_relatorio,
    preprocessar,
)

__all__ = [
    "preprocessar",
    "extrair_contrato",
    "compilar_extracao",
    "analisar_contrato",
    "gerar_relatorio",
]
