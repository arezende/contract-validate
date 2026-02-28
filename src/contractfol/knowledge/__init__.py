"""
Base de Conhecimento Legal do ContractFOL.

Contém regras legais codificadas para detecção de cláusulas abusivas
em contratos B2B conforme legislação brasileira.
"""

from contractfol.knowledge.legal_rules import LegalRule, get_legal_rules

__all__ = ["LegalRule", "get_legal_rules"]
