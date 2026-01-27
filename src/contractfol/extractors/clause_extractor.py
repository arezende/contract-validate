"""
Extrator de Cláusulas Contratuais.

Implementa a extração de cláusulas de documentos contratuais usando regras
heurísticas e padrões de regex para identificar marcadores típicos de
cláusulas em português brasileiro.

Conforme Seção 5.3 da dissertação:
- Regras identificam marcadores típicos ("Cláusula Primeira", "Art. 1º", etc.)
- A saída é uma lista de objetos Cláusula com identificador, texto integral,
  referência à seção pai e metadados extraídos.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Iterator

from contractfol.models import Agent, Clause, Contract


@dataclass
class ExtractionPattern:
    """Padrão de extração de cláusulas."""

    name: str
    pattern: re.Pattern
    priority: int = 0


class ClauseExtractor:
    """
    Extrator de cláusulas contratuais.

    Utiliza uma combinação de regras heurísticas e padrões de regex
    para segmentar contratos em cláusulas individuais.
    """

    # Padrões para identificação de cláusulas em português
    CLAUSE_PATTERNS = [
        # Cláusula Primeira, Cláusula Segunda, etc.
        ExtractionPattern(
            "clausula_ordinal",
            re.compile(
                r"^[\s]*CLÁUSULA\s+(PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|"
                r"SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|DÉCIMA\s+PRIMEIRA|"
                r"DÉCIMA\s+SEGUNDA|DÉCIMA\s+TERCEIRA|DÉCIMA\s+QUARTA|"
                r"DÉCIMA\s+QUINTA|VIGÉSIMA|TRIGÉSIMA|QUADRAGÉSIMA|"
                r"QUINQUAGÉSIMA)[\s–\-:]*(.+)?",
                re.IGNORECASE | re.MULTILINE,
            ),
            priority=10,
        ),
        # Cláusula 1ª, Cláusula 2ª, etc.
        ExtractionPattern(
            "clausula_numeral_ordinal",
            re.compile(
                r"^[\s]*CLÁUSULA\s+(\d+)[ªºa][\s–\-:]*(.+)?", re.IGNORECASE | re.MULTILINE
            ),
            priority=9,
        ),
        # CLÁUSULA 1 - TÍTULO
        ExtractionPattern(
            "clausula_numeral",
            re.compile(r"^[\s]*CLÁUSULA\s+(\d+)[\s–\-:]+(.+)?", re.IGNORECASE | re.MULTILINE),
            priority=8,
        ),
        # Art. 1º, Art. 2º, etc.
        ExtractionPattern(
            "artigo",
            re.compile(r"^[\s]*Art\.?\s*(\d+)[ºª]?[\s–\-:\.]+(.+)?", re.IGNORECASE | re.MULTILINE),
            priority=7,
        ),
        # 1. Texto, 2. Texto (numeração simples)
        ExtractionPattern(
            "numeracao_simples",
            re.compile(r"^[\s]*(\d+)\.\s+([A-Z].+)", re.MULTILINE),
            priority=5,
        ),
        # I - Texto, II - Texto (numeração romana)
        ExtractionPattern(
            "numeracao_romana",
            re.compile(
                r"^[\s]*(I{1,3}|IV|V|VI{1,3}|IX|X|XI{1,3}|XIV|XV|"
                r"XVI{1,3}|XIX|XX)\s*[\-–\.]\s*(.+)",
                re.MULTILINE,
            ),
            priority=4,
        ),
        # Parágrafo Único, § 1º, etc.
        ExtractionPattern(
            "paragrafo",
            re.compile(
                r"^[\s]*(§\s*\d+[ºª]?|PARÁGRAFO\s+(ÚNICO|PRIMEIRO|SEGUNDO|"
                r"TERCEIRO|\d+[ºª]?))[\s–\-:\.]*(.+)?",
                re.IGNORECASE | re.MULTILINE,
            ),
            priority=3,
        ),
        # Alíneas: a), b), c)
        ExtractionPattern(
            "alinea",
            re.compile(r"^[\s]*([a-z])\)\s+(.+)", re.MULTILINE),
            priority=2,
        ),
    ]

    # Padrões para identificação de partes/agentes
    AGENT_PATTERNS = [
        # CONTRATANTE, CONTRATADO, PATROCINADOR, etc.
        re.compile(
            r"\b(CONTRATANTE|CONTRATADO|CONTRATADA|PATROCINADOR|PATROCINADORA|"
            r"PATROCINADO|CEDENTE|CESSIONÁRIO|CESSIONÁRIA|LICENCIANTE|"
            r"LICENCIADO|LICENCIADA|ATLETA|CONFEDERAÇÃO|FEDERAÇÃO|COB|"
            r"COMITÊ\s+OLÍMPICO|FORNECEDOR|PRESTADOR|TOMADOR)\b",
            re.IGNORECASE,
        ),
    ]

    def __init__(self, min_clause_length: int = 20, max_clause_length: int = 5000):
        """
        Inicializa o extrator.

        Args:
            min_clause_length: Comprimento mínimo para considerar como cláusula
            max_clause_length: Comprimento máximo para uma única cláusula
        """
        self.min_clause_length = min_clause_length
        self.max_clause_length = max_clause_length

    def extract_from_text(self, text: str, contract_id: str | None = None) -> Contract:
        """
        Extrai cláusulas de um texto de contrato.

        Args:
            text: Texto completo do contrato
            contract_id: ID do contrato (gerado automaticamente se não fornecido)

        Returns:
            Objeto Contract com as cláusulas extraídas
        """
        if not contract_id:
            contract_id = str(uuid.uuid4())[:8]

        contract = Contract(
            id=contract_id,
            title=self._extract_title(text),
        )

        # Extrair partes do contrato
        contract.parties = self._extract_parties(text)

        # Encontrar todas as posições de início de cláusulas
        clause_positions = self._find_clause_positions(text)

        # Segmentar o texto em cláusulas
        clauses = self._segment_clauses(text, clause_positions, contract_id)

        contract.clauses = clauses
        contract.processed = True

        return contract

    def _extract_title(self, text: str) -> str:
        """Extrai o título do contrato."""
        # Tentar encontrar título no início do documento
        patterns = [
            re.compile(
                r"^[\s]*(CONTRATO\s+DE\s+[A-ZÀ-ÚÇ\s]+)", re.IGNORECASE | re.MULTILINE
            ),
            re.compile(r"^[\s]*(TERMO\s+DE\s+[A-ZÀ-ÚÇ\s]+)", re.IGNORECASE | re.MULTILINE),
            re.compile(r"^[\s]*(ACORDO\s+DE\s+[A-ZÀ-ÚÇ\s]+)", re.IGNORECASE | re.MULTILINE),
            re.compile(
                r"^[\s]*(INSTRUMENTO\s+PARTICULAR\s+DE\s+[A-ZÀ-ÚÇ\s]+)",
                re.IGNORECASE | re.MULTILINE,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(text[:2000])  # Procurar no início
            if match:
                title = match.group(1).strip()
                # Limitar tamanho do título
                if len(title) > 150:
                    title = title[:150] + "..."
                return title

        return "Contrato sem título identificado"

    def _extract_parties(self, text: str) -> list[Agent]:
        """Extrai as partes/agentes mencionados no contrato."""
        agents = []
        seen_roles = set()

        # Procurar por padrões de identificação de partes
        for pattern in self.AGENT_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                role = match.upper().strip()
                if role not in seen_roles:
                    seen_roles.add(role)
                    agent = Agent(
                        id=f"agent_{len(agents) + 1}",
                        name=role,
                        role=role,
                    )
                    agents.append(agent)

        return agents

    def _find_clause_positions(self, text: str) -> list[tuple[int, str, str]]:
        """
        Encontra todas as posições de início de cláusulas no texto.

        Returns:
            Lista de tuplas (posição, tipo_padrão, número/identificador)
        """
        positions = []

        for pattern_def in self.CLAUSE_PATTERNS:
            for match in pattern_def.pattern.finditer(text):
                positions.append(
                    (
                        match.start(),
                        pattern_def.name,
                        match.group(1) if match.lastindex >= 1 else "",
                        pattern_def.priority,
                    )
                )

        # Ordenar por posição
        positions.sort(key=lambda x: x[0])

        return positions

    def _segment_clauses(
        self, text: str, positions: list[tuple], contract_id: str
    ) -> list[Clause]:
        """
        Segmenta o texto em cláusulas baseado nas posições encontradas.
        """
        clauses = []

        if not positions:
            # Se não encontrou padrões, tenta dividir por parágrafos
            return self._segment_by_paragraphs(text, contract_id)

        # Processar cada posição
        for i, (pos, pattern_type, identifier, priority) in enumerate(positions):
            # Determinar o fim da cláusula (início da próxima ou fim do texto)
            if i + 1 < len(positions):
                end_pos = positions[i + 1][0]
            else:
                end_pos = len(text)

            clause_text = text[pos:end_pos].strip()

            # Validar tamanho
            if len(clause_text) < self.min_clause_length:
                continue

            if len(clause_text) > self.max_clause_length:
                clause_text = clause_text[: self.max_clause_length] + "..."

            # Criar objeto Clause
            clause = Clause(
                id=f"{contract_id}_clause_{len(clauses) + 1}",
                text=clause_text,
                contract_id=contract_id,
                number=str(identifier) if identifier else str(len(clauses) + 1),
                section=pattern_type,
            )

            # Extrair agentes mencionados na cláusula
            clause.agents = self._extract_clause_agents(clause_text)

            clauses.append(clause)

        return clauses

    def _segment_by_paragraphs(self, text: str, contract_id: str) -> list[Clause]:
        """
        Segmenta por parágrafos quando não há padrões de cláusula.
        """
        clauses = []
        paragraphs = text.split("\n\n")

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) >= self.min_clause_length:
                clause = Clause(
                    id=f"{contract_id}_para_{i + 1}",
                    text=para[: self.max_clause_length],
                    contract_id=contract_id,
                    number=str(i + 1),
                    section="paragraph",
                )
                clause.agents = self._extract_clause_agents(para)
                clauses.append(clause)

        return clauses

    def _extract_clause_agents(self, text: str) -> list[Agent]:
        """Extrai agentes mencionados em uma cláusula específica."""
        agents = []
        seen = set()

        for pattern in self.AGENT_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                role = match.upper().strip()
                if role not in seen:
                    seen.add(role)
                    agents.append(Agent(id=f"agent_{role.lower()}", name=role, role=role))

        return agents

    def extract_from_contract(self, contract: Contract, text: str) -> Contract:
        """
        Extrai cláusulas e atualiza um objeto Contract existente.
        """
        extracted = self.extract_from_text(text, contract.id)
        contract.clauses = extracted.clauses
        contract.parties = extracted.parties or contract.parties
        contract.processed = True
        return contract


def extract_clauses(text: str, contract_id: str | None = None) -> list[Clause]:
    """
    Função utilitária para extrair cláusulas de um texto.

    Args:
        text: Texto do contrato
        contract_id: ID opcional do contrato

    Returns:
        Lista de cláusulas extraídas
    """
    extractor = ClauseExtractor()
    contract = extractor.extract_from_text(text, contract_id)
    return contract.clauses
