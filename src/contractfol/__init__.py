"""
ContractFOL - Validação Automatizada de Contratos Inter-Institucionais
utilizando Large Language Models e Lógica de Primeira Ordem.

Este módulo implementa o artefato proposto na dissertação de mestrado
"Validação Automatizada de Contratos Inter-Institucionais Utilizando
Large Language Models e Lógica de Primeira Ordem: Uma Abordagem
Design Science Research" - Anderson Rezende, COPPE/UFRJ, 2025.

Extensões:
- Ontologia Dinâmica: Permite descoberta automática de predicados
- Base de Conhecimento: Armazena fatos e permite inferência
- Descoberta de Predicados: Gera novos predicados a partir do texto
"""

__version__ = "0.2.0"
__author__ = "Anderson Rezende"

from contractfol.pipeline import ContractFOLPipeline
from contractfol.ontology import ContractOntology
from contractfol.dynamic_ontology import DynamicOntology, get_dynamic_ontology
from contractfol.knowledge_base import KnowledgeBase, get_knowledge_base
from contractfol.predicate_discovery import PredicateDiscovery, discover_predicates

__all__ = [
    "ContractFOLPipeline",
    "ContractOntology",
    "DynamicOntology",
    "get_dynamic_ontology",
    "KnowledgeBase",
    "get_knowledge_base",
    "PredicateDiscovery",
    "discover_predicates",
    "__version__",
]
