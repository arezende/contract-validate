"""Core modules — ContractFOL V3."""

from .e1_preprocessor import preprocessar
from .e2_extractor import extrair_contrato
from .e3_compiler import compilar_extracao
from .e4_analyzer import analisar_contrato
from .e5_reporter import gerar_relatorio

__all__ = [
    "preprocessar",
    "extrair_contrato",
    "compilar_extracao",
    "analisar_contrato",
    "gerar_relatorio",
]
