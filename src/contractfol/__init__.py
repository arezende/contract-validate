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

from contractfol.detectors import AbusiveClauseDetector
from contractfol.ontology import ContractOntology
from contractfol.pipeline import ContractFOLPipeline

__all__ = [
    "ContractFOLPipeline",
    "ContractOntology",
    "AbusiveClauseDetector",
    "__version__",
]
