"""
ContractFOL - Validação Automatizada de Contratos Inter-Institucionais
utilizando Large Language Models e Lógica de Primeira Ordem.

Este módulo implementa o artefato proposto na dissertação de mestrado
"Validação Automatizada de Contratos Inter-Institucionais Utilizando
Large Language Models e Lógica de Primeira Ordem: Uma Abordagem
Design Science Research" - Anderson Rezende, COPPE/UFRJ, 2025.
"""

__version__ = "0.1.0"
__author__ = "Anderson Rezende"

from contractfol.contractfol import (
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
    "__version__",
]
