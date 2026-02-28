"""
Modelos de dados do ContractFOL.

Define as estruturas de dados utilizadas em todo o pipeline de validação contratual.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class DeonticModality(Enum):
    """Modalidades deônticas conforme Von Wright (1951)."""

    OBRIGACAO_ATIVA = "OBRIGACAO_ATIVA"      # Agente deve fazer algo
    OBRIGACAO_PASSIVA = "OBRIGACAO_PASSIVA"  # Agente deve permitir algo
    PERMISSAO = "PERMISSAO"                   # Agente pode fazer algo
    PROIBICAO = "PROIBICAO"                   # Agente não pode fazer algo
    CONDICAO = "CONDICAO"                     # Cláusula condicional
    DEFINICAO = "DEFINICAO"                   # Cláusula definitória


class ConflictType(Enum):
    """Tipos de conflitos detectáveis."""

    OBRIGACAO_PROIBICAO = "OBRIGACAO_PROIBICAO"      # Obrigado e proibido ao mesmo tempo
    OBRIGACOES_MUTUAMENTE_EXCLUSIVAS = "OBRIGACOES_MUTUAMENTE_EXCLUSIVAS"
    PRAZO_INCONSISTENTE = "PRAZO_INCONSISTENTE"       # Prazos contraditórios
    CONDICAO_IMPOSSIVEL = "CONDICAO_IMPOSSIVEL"       # Condição impossível de satisfazer
    AGENTE_AMBIGUO = "AGENTE_AMBIGUO"                 # Agente não claramente identificado
    VALOR_INCONSISTENTE = "VALOR_INCONSISTENTE"       # Valores monetários conflitantes


class AbusiveClauseType(Enum):
    """Tipos de cláusulas abusivas conforme legislação brasileira (foco B2B)."""

    # Código Civil - Princípios gerais e contratos empresariais
    EXCLUSAO_RESPONSABILIDADE = "EXCLUSAO_RESPONSABILIDADE"       # CC Art. 424, 393
    RESCISAO_UNILATERAL = "RESCISAO_UNILATERAL"                   # CC Art. 473
    MODIFICACAO_UNILATERAL = "MODIFICACAO_UNILATERAL"             # CC Art. 421, 422
    MULTA_EXCESSIVA = "MULTA_EXCESSIVA"                           # CC Art. 412, 413
    RENUNCIA_DIREITO = "RENUNCIA_DIREITO"                         # CC Art. 424
    DESVANTAGEM_EXAGERADA = "DESVANTAGEM_EXAGERADA"               # CC Art. 157 (lesão)
    ONEROSIDADE_EXCESSIVA = "ONEROSIDADE_EXCESSIVA"               # CC Art. 478-480
    BOA_FE_VIOLACAO = "BOA_FE_VIOLACAO"                           # CC Art. 113, 422
    CLAUSULA_LEONINA = "CLAUSULA_LEONINA"                         # CC Art. 1.008 (sociedade)
    PERDA_PRESTACOES = "PERDA_PRESTACOES"                         # CC Art. 413
    TRANSFERENCIA_RESPONSABILIDADE = "TRANSFERENCIA_RESPONSABILIDADE"  # CC Art. 424
    INDENIZACAO_DESPROPORCIONAL = "INDENIZACAO_DESPROPORCIONAL"   # CC Art. 944
    # CDC por analogia (contratos de adesão empresarial)
    ARBITRAGEM_COMPULSORIA = "ARBITRAGEM_COMPULSORIA"             # CDC Art. 51 VII (analogia)
    ALTERACAO_PRECO_UNILATERAL = "ALTERACAO_PRECO_UNILATERAL"     # CDC Art. 51 X (analogia)
    # Geral
    OUTRA_ABUSIVIDADE = "OUTRA_ABUSIVIDADE"


class VerificationStatus(Enum):
    """Status da verificação formal."""

    SAT = "SAT"           # Satisfatível - sem conflitos
    UNSAT = "UNSAT"       # Insatisfatível - conflito detectado
    UNKNOWN = "UNKNOWN"   # Indeterminado
    ERROR = "ERROR"       # Erro no processamento


@dataclass
class Agent:
    """Representa um agente/parte contratual."""

    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    role: Optional[str] = None  # CONTRATANTE, CONTRATADO, PATROCINADOR, etc.

    def matches(self, text: str) -> bool:
        """Verifica se o texto corresponde a este agente."""
        text_lower = text.lower()
        if self.name.lower() in text_lower:
            return True
        return any(alias.lower() in text_lower for alias in self.aliases)


@dataclass
class Clause:
    """Representa uma cláusula contratual extraída."""

    id: str
    text: str
    contract_id: str
    section: Optional[str] = None
    number: Optional[str] = None
    parent_clause_id: Optional[str] = None

    # Metadados extraídos
    agents: list[Agent] = field(default_factory=list)
    modality: Optional[DeonticModality] = None
    modality_confidence: float = 0.0

    # Representação FOL
    fol_formula: Optional[str] = None
    fol_parsed: bool = False
    fol_translation_attempts: int = 0


@dataclass
class Contract:
    """Representa um contrato completo."""

    id: str
    title: str
    file_path: Optional[str] = None

    # Partes do contrato
    parties: list[Agent] = field(default_factory=list)

    # Metadados
    date_signed: Optional[date] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    contract_type: Optional[str] = None  # PATROCINIO, FORNECIMENTO, etc.

    # Cláusulas extraídas
    clauses: list[Clause] = field(default_factory=list)

    # Status de processamento
    processed: bool = False

    @property
    def clause_count(self) -> int:
        return len(self.clauses)


@dataclass
class FOLFormula:
    """Representa uma fórmula em Lógica de Primeira Ordem."""

    clause_id: str
    original_text: str
    formula: str

    # Metadados da tradução
    predicates_used: list[str] = field(default_factory=list)
    constants_used: list[str] = field(default_factory=list)
    variables_used: list[str] = field(default_factory=list)

    # Validação
    syntactically_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    """Representa um conflito detectado entre cláusulas."""

    id: str
    conflict_type: ConflictType

    # Cláusulas envolvidas
    clause_ids: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)

    # Resultado da verificação Z3
    unsat_core: list[str] = field(default_factory=list)

    # Explicação
    explanation: Optional[str] = None
    suggestion: Optional[str] = None

    # Metadados
    severity: str = "HIGH"  # HIGH, MEDIUM, LOW
    confidence: float = 1.0


@dataclass
class AbusiveClauseViolation:
    """Representa uma violação detectada em cláusula individual."""

    id: str
    clause_id: str
    violation_type: AbusiveClauseType

    # Fundamentação legal
    legal_basis: str  # Ex: "CC, Art. 424"
    description: str
    suggestion: str

    # Metadados
    severity: str = "HIGH"  # HIGH, MEDIUM, LOW
    confidence: float = 1.0
    detection_layer: str = "heuristic"  # "heuristic", "formal", "llm"

    # Explicação gerada (preenchida pelo ExplanationGenerator)
    explanation: Optional[str] = None


@dataclass
class ValidationReport:
    """Relatório completo de validação contratual."""

    contract_ids: list[str]

    # Resultados
    status: VerificationStatus = VerificationStatus.UNKNOWN
    conflicts: list[Conflict] = field(default_factory=list)
    abusive_clauses: list[AbusiveClauseViolation] = field(default_factory=list)

    # Estatísticas
    total_clauses: int = 0
    clauses_translated: int = 0
    translation_success_rate: float = 0.0

    # Tempo de processamento
    extraction_time_ms: float = 0.0
    classification_time_ms: float = 0.0
    abusive_detection_time_ms: float = 0.0
    translation_time_ms: float = 0.0
    verification_time_ms: float = 0.0
    total_time_ms: float = 0.0

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def has_abusive_clauses(self) -> bool:
        return len(self.abusive_clauses) > 0

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def abusive_clause_count(self) -> int:
        return len(self.abusive_clauses)
