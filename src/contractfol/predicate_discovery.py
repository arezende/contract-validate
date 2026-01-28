"""
Descoberta Dinâmica de Predicados ContractFOL.

Módulo responsável por descobrir novos predicados automaticamente
a partir da análise do texto do contrato usando LLMs.

O processo de descoberta:
1. Análise do texto para identificar conceitos não cobertos
2. Proposta de novos predicados via LLM
3. Validação semântica dos predicados propostos
4. Registro na ontologia dinâmica

Predicados Base (referência):
- Obrigacao(a, p, t): Agente a é obrigado a realizar p até tempo t
- Permissao(a, p): Agente a tem permissão para p
- Proibicao(a, p): Agente a é proibido de realizar p
- Parte(x, c): Entidade x é parte do contrato c
- Prazo(c, d1, d2): Contrato c tem vigência de d1 a d2
- Condicao(p, q): Condição p implica consequência q
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from contractfol.dynamic_ontology import (
    DynamicOntology,
    DynamicPredicate,
    get_dynamic_ontology,
)


@dataclass
class PredicateProposal:
    """Proposta de um novo predicado."""

    name: str
    arity: int
    description: str
    argument_types: list[str]
    argument_names: list[str]
    examples: list[str]
    justification: str  # Por que este predicado é necessário
    source_text: str  # Texto que motivou a proposta
    confidence: float = 0.0
    semantic_tags: list[str] = field(default_factory=list)
    related_predicates: list[str] = field(default_factory=list)
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    """Resultado de uma sessão de descoberta de predicados."""

    source_text: str
    proposals: list[PredicateProposal]
    accepted: list[str]  # Nomes dos predicados aceitos
    rejected: list[str]  # Nomes dos predicados rejeitados
    existing_coverage: list[str]  # Predicados existentes que já cobrem
    analysis_notes: str = ""


class PredicateDiscovery:
    """
    Sistema de descoberta automática de predicados.

    Usa LLMs para analisar textos contratuais e propor novos predicados
    quando os existentes não são suficientes para representar a semântica.
    """

    # Tipos válidos para argumentos de predicados
    VALID_TYPES = {
        "Agente", "Agent",
        "Acao", "Action",
        "Tempo", "Time",
        "Data", "Date",
        "Contrato", "Contract",
        "Valor", "Value",
        "Real", "Int", "String", "Bool",
        "Resource", "Recurso",
        "Condicao", "Condition",
    }

    # Padrões comuns em contratos brasileiros que podem indicar novos predicados
    CONCEPT_PATTERNS = {
        "garantia": r"garant[ie]|caução|fiança|aval",
        "penalidade": r"multa|penalidade|sanção|infração",
        "rescisão": r"rescis|cancel|termin|extingu|distrat",
        "renovação": r"renov|prorro|extend",
        "confidencialidade": r"confidencial|sigilo|reserva|segredo",
        "cessão": r"cess[ãa]o|transfer|repassa|subloc",
        "notificação": r"notific|comunic|aviso|cientific",
        "arbitragem": r"arbitr|mediação|conciliação",
        "foro": r"foro|jurisdição|competência",
        "testemunha": r"testemunha|presenci",
        "anexo": r"anexo|adendo|apenso",
        "reajuste": r"reajust|correção|atualização monetária|índice",
        "vigência": r"vigência|duração|período|termo",
        "objeto": r"objeto|finalidade|escopo",
        "representante": r"representante|procurador|mandatário",
        "solidariedade": r"solidári|conjunt|subsidiári",
    }

    def __init__(
        self,
        llm_client: Any | None = None,
        model: str = "gpt-4",
        ontology: DynamicOntology | None = None,
        auto_register: bool = False,
        min_confidence: float = 0.7,
    ):
        """
        Inicializa o descobridor de predicados.

        Args:
            llm_client: Cliente LLM (OpenAI, Anthropic ou Gemini)
            model: Nome do modelo
            ontology: Ontologia dinâmica para registrar predicados
            auto_register: Se True, registra predicados automaticamente
            min_confidence: Confiança mínima para aceitar um predicado
        """
        self.llm_client = llm_client
        self.model = model
        self.ontology = ontology or get_dynamic_ontology()
        self.auto_register = auto_register
        self.min_confidence = min_confidence

    def analyze_text(self, text: str) -> DiscoveryResult:
        """
        Analisa um texto e descobre predicados necessários.

        Args:
            text: Texto do contrato ou cláusula

        Returns:
            Resultado da descoberta com propostas de predicados
        """
        # 1. Identificar conceitos não cobertos
        uncovered_concepts = self._identify_uncovered_concepts(text)

        # 2. Verificar cobertura existente
        existing_coverage = self._check_existing_coverage(text)

        # 3. Se não há conceitos novos, retornar vazio
        if not uncovered_concepts:
            return DiscoveryResult(
                source_text=text,
                proposals=[],
                accepted=[],
                rejected=[],
                existing_coverage=existing_coverage,
                analysis_notes="Todos os conceitos estão cobertos pela ontologia atual.",
            )

        # 4. Propor predicados via LLM
        if self.llm_client:
            proposals = self._propose_predicates_llm(text, uncovered_concepts)
        else:
            proposals = self._propose_predicates_heuristic(text, uncovered_concepts)

        # 5. Validar propostas
        for proposal in proposals:
            self._validate_proposal(proposal)

        # 6. Registrar predicados aceitos
        accepted = []
        rejected = []

        for proposal in proposals:
            if proposal.is_valid and proposal.confidence >= self.min_confidence:
                if self.auto_register:
                    self._register_predicate(proposal)
                accepted.append(proposal.name)
            else:
                rejected.append(proposal.name)

        return DiscoveryResult(
            source_text=text,
            proposals=proposals,
            accepted=accepted,
            rejected=rejected,
            existing_coverage=existing_coverage,
        )

    def _identify_uncovered_concepts(self, text: str) -> list[tuple[str, str]]:
        """
        Identifica conceitos no texto que não estão na ontologia.

        Returns:
            Lista de (nome_conceito, trecho_relevante)
        """
        text_lower = text.lower()
        uncovered = []

        for concept, pattern in self.CONCEPT_PATTERNS.items():
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                # Verificar se não há predicado existente para este conceito
                if not self._has_existing_predicate(concept):
                    # Extrair contexto ao redor do match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    uncovered.append((concept, context))
                    break  # Um match por conceito é suficiente

        return uncovered

    def _has_existing_predicate(self, concept: str) -> bool:
        """Verifica se já existe um predicado para o conceito."""
        concept_lower = concept.lower()

        for name in self.ontology.list_predicates():
            if concept_lower in name.lower():
                return True

            pred = self.ontology.get_predicate(name)
            if pred and concept_lower in pred.description.lower():
                return True

        return False

    def _check_existing_coverage(self, text: str) -> list[str]:
        """Retorna predicados existentes que cobrem o texto."""
        covered = []
        text_lower = text.lower()

        # Mapear palavras-chave para predicados
        keyword_to_predicate = {
            "obriga": "Obrigacao",
            "dever": "Obrigacao",
            "deve": "Obrigacao",
            "compromete": "Obrigacao",
            "permite": "Permissao",
            "pode": "Permissao",
            "faculta": "Permissao",
            "proíbe": "Proibicao",
            "proib": "Proibicao",
            "veda": "Proibicao",
            "não poderá": "Proibicao",
            "não pode": "Proibicao",
            "prazo": "Prazo",
            "vigência": "Prazo",
            "condição": "Condicao",
            "caso": "Condicao",
            "se ": "Condicao",
            "paga": "Pagamento",
            "valor": "Valor",
            "marca": "UsoMarca",
            "imagem": "UsoImagem",
            "exclusiv": "Exclusividade",
        }

        for keyword, pred in keyword_to_predicate.items():
            if keyword in text_lower and pred not in covered:
                covered.append(pred)

        return covered

    def _propose_predicates_llm(
        self,
        text: str,
        uncovered_concepts: list[tuple[str, str]]
    ) -> list[PredicateProposal]:
        """Usa LLM para propor novos predicados."""
        prompt = self._build_discovery_prompt(text, uncovered_concepts)
        response = self._call_llm(prompt)
        return self._parse_llm_proposals(response, text)

    def _build_discovery_prompt(
        self,
        text: str,
        uncovered_concepts: list[tuple[str, str]]
    ) -> str:
        """Constrói prompt para descoberta de predicados."""
        existing_preds = "\n".join([
            f"- {pred.signature()}: {pred.description}"
            for pred in self.ontology.predicates.values()
        ])

        concepts_str = "\n".join([
            f"- {concept}: ...{context}..."
            for concept, context in uncovered_concepts
        ])

        return f"""Você é um especialista em modelagem de conhecimento jurídico e lógica formal.

## Ontologia Atual
A ontologia atual possui os seguintes predicados:
{existing_preds}

## Texto para Análise
{text}

## Conceitos Identificados (possivelmente não cobertos)
{concepts_str}

## Tarefa
Analise o texto e proponha NOVOS predicados para conceitos que NÃO estão adequadamente
cobertos pela ontologia atual. Para cada predicado proposto, forneça:

1. Nome em PascalCase (ex: GarantiaContratual)
2. Aridade (número de argumentos)
3. Descrição em português
4. Tipos dos argumentos (de: Agente, Acao, Tempo, Contrato, Valor, Data, String, Bool)
5. Nomes dos argumentos
6. 2-3 exemplos de uso
7. Justificativa de por que este predicado é necessário
8. Tags semânticas (deontico, temporal, estrutural, condicional, acao, valor)
9. Predicados relacionados da ontologia atual

## Formato de Resposta
Responda em JSON com o seguinte formato:
```json
{{
  "proposals": [
    {{
      "name": "NomePredicado",
      "arity": 2,
      "description": "Descrição do predicado",
      "argument_types": ["Agente", "Valor"],
      "argument_names": ["agente", "valor"],
      "examples": ["NomePredicado(x, y)", "NomePredicado(a, b)"],
      "justification": "Este predicado é necessário porque...",
      "semantic_tags": ["deontico"],
      "related_predicates": ["Obrigacao", "Valor"],
      "confidence": 0.85
    }}
  ],
  "analysis_notes": "Notas sobre a análise..."
}}
```

Se NENHUM novo predicado for necessário, retorne:
```json
{{
  "proposals": [],
  "analysis_notes": "A ontologia atual é suficiente porque..."
}}
```

Resposta JSON:"""

    def _call_llm(self, prompt: str) -> str:
        """Chama o LLM para obter propostas."""
        try:
            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                # OpenAI
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                )
                return response.choices[0].message.content

            elif hasattr(self.llm_client, "messages"):
                # Anthropic
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text

            elif hasattr(self.llm_client, "generate_content"):
                # Gemini
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 2000,
                    },
                )
                return response.text

            else:
                return "{}"

        except Exception as e:
            return f'{{"error": "{e}"}}'

    def _parse_llm_proposals(
        self,
        response: str,
        source_text: str
    ) -> list[PredicateProposal]:
        """Parse da resposta do LLM em propostas de predicados."""
        proposals = []

        try:
            # Extrair JSON da resposta
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return proposals

            data = json.loads(json_match.group())

            for p in data.get("proposals", []):
                proposal = PredicateProposal(
                    name=p.get("name", ""),
                    arity=p.get("arity", 0),
                    description=p.get("description", ""),
                    argument_types=p.get("argument_types", []),
                    argument_names=p.get("argument_names", []),
                    examples=p.get("examples", []),
                    justification=p.get("justification", ""),
                    source_text=source_text,
                    confidence=p.get("confidence", 0.5),
                    semantic_tags=p.get("semantic_tags", []),
                    related_predicates=p.get("related_predicates", []),
                )
                proposals.append(proposal)

        except (json.JSONDecodeError, KeyError):
            pass

        return proposals

    def _propose_predicates_heuristic(
        self,
        text: str,
        uncovered_concepts: list[tuple[str, str]]
    ) -> list[PredicateProposal]:
        """Gera propostas heurísticas sem LLM."""
        proposals = []

        # Templates para conceitos comuns
        concept_templates = {
            "garantia": {
                "name": "Garantia",
                "arity": 3,
                "description": "Agente oferece garantia de tipo para contrato",
                "argument_types": ["Agente", "String", "Contrato"],
                "argument_names": ["garantidor", "tipo_garantia", "contrato"],
                "examples": ["Garantia(contratado, caucao, contrato_001)"],
                "semantic_tags": ["estrutural"],
            },
            "penalidade": {
                "name": "Penalidade",
                "arity": 3,
                "description": "Penalidade aplicável a agente por infração",
                "argument_types": ["Agente", "String", "Valor"],
                "argument_names": ["agente", "infracao", "valor"],
                "examples": ["Penalidade(contratado, atraso, 1000.00)"],
                "semantic_tags": ["deontico", "valor"],
            },
            "rescisão": {
                "name": "Rescisao",
                "arity": 3,
                "description": "Rescisão de contrato por agente com motivo",
                "argument_types": ["Contrato", "Agente", "String"],
                "argument_names": ["contrato", "agente", "motivo"],
                "examples": ["Rescisao(contrato_001, contratante, inadimplencia)"],
                "semantic_tags": ["estrutural"],
            },
            "renovação": {
                "name": "Renovacao",
                "arity": 3,
                "description": "Renovação de contrato por período",
                "argument_types": ["Contrato", "Tempo", "Tempo"],
                "argument_names": ["contrato", "inicio_renovacao", "fim_renovacao"],
                "examples": ["Renovacao(contrato_001, 2025-01-01, 2025-12-31)"],
                "semantic_tags": ["temporal", "estrutural"],
            },
            "confidencialidade": {
                "name": "Confidencialidade",
                "arity": 2,
                "description": "Agente está sujeito a confidencialidade sobre informação",
                "argument_types": ["Agente", "String"],
                "argument_names": ["agente", "informacao"],
                "examples": ["Confidencialidade(contratado, dados_comerciais)"],
                "semantic_tags": ["deontico"],
            },
            "cessão": {
                "name": "Cessao",
                "arity": 4,
                "description": "Cessão de direitos/obrigações de agente para outro",
                "argument_types": ["Agente", "Agente", "String", "Contrato"],
                "argument_names": ["cedente", "cessionario", "objeto", "contrato"],
                "examples": ["Cessao(contratado, terceiro, direitos, contrato_001)"],
                "semantic_tags": ["estrutural"],
            },
            "notificação": {
                "name": "Notificacao",
                "arity": 4,
                "description": "Notificação de agente para outro sobre assunto em prazo",
                "argument_types": ["Agente", "Agente", "String", "Tempo"],
                "argument_names": ["notificante", "notificado", "assunto", "prazo"],
                "examples": ["Notificacao(contratante, contratado, rescisao, 30_dias)"],
                "semantic_tags": ["acao", "temporal"],
            },
            "reajuste": {
                "name": "Reajuste",
                "arity": 3,
                "description": "Reajuste de valor por índice em periodicidade",
                "argument_types": ["Valor", "String", "Tempo"],
                "argument_names": ["valor", "indice", "periodicidade"],
                "examples": ["Reajuste(mensalidade, IGPM, anual)"],
                "semantic_tags": ["valor", "temporal"],
            },
        }

        for concept, context in uncovered_concepts:
            if concept in concept_templates:
                template = concept_templates[concept]
                proposal = PredicateProposal(
                    name=template["name"],
                    arity=template["arity"],
                    description=template["description"],
                    argument_types=template["argument_types"],
                    argument_names=template["argument_names"],
                    examples=template["examples"],
                    justification=f"Conceito '{concept}' identificado no texto mas não coberto pela ontologia",
                    source_text=context,
                    confidence=0.75,
                    semantic_tags=template["semantic_tags"],
                    related_predicates=self._find_related(template["semantic_tags"]),
                )
                proposals.append(proposal)

        return proposals

    def _find_related(self, semantic_tags: list[str]) -> list[str]:
        """Encontra predicados relacionados pelos tags."""
        related = []
        for pred in self.ontology.dynamic_predicates.values():
            for tag in semantic_tags:
                if tag == pred.metadata.domain:
                    related.append(pred.name)
                    break
        return related[:5]  # Limitar a 5

    def _validate_proposal(self, proposal: PredicateProposal):
        """Valida uma proposta de predicado."""
        errors = []

        # Validar nome
        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", proposal.name):
            errors.append(f"Nome inválido: {proposal.name}. Use PascalCase.")

        # Verificar se já existe
        if proposal.name in self.ontology.predicates:
            errors.append(f"Predicado '{proposal.name}' já existe na ontologia.")

        # Validar aridade
        if proposal.arity != len(proposal.argument_types):
            errors.append(
                f"Aridade ({proposal.arity}) não corresponde ao número de tipos "
                f"({len(proposal.argument_types)})"
            )
        if proposal.arity != len(proposal.argument_names):
            errors.append(
                f"Aridade ({proposal.arity}) não corresponde ao número de nomes "
                f"({len(proposal.argument_names)})"
            )

        # Validar tipos
        for t in proposal.argument_types:
            if t not in self.VALID_TYPES:
                errors.append(f"Tipo inválido: {t}. Tipos válidos: {self.VALID_TYPES}")

        # Validar descrição
        if len(proposal.description) < 10:
            errors.append("Descrição muito curta (mínimo 10 caracteres)")

        # Atualizar proposta
        proposal.validation_errors = errors
        proposal.is_valid = len(errors) == 0

    def _register_predicate(self, proposal: PredicateProposal):
        """Registra um predicado proposto na ontologia."""
        self.ontology.add_predicate(
            name=proposal.name,
            arity=proposal.arity,
            description=proposal.description,
            argument_types=proposal.argument_types,
            argument_names=proposal.argument_names,
            examples=proposal.examples,
            source_clause=proposal.source_text,
            confidence=proposal.confidence,
            semantic_tags=proposal.semantic_tags,
            related_predicates=proposal.related_predicates,
        )

    def discover_from_contract(
        self,
        clauses: list[dict],
        contract_id: str = ""
    ) -> list[DiscoveryResult]:
        """
        Descobre predicados a partir de múltiplas cláusulas.

        Args:
            clauses: Lista de dicts com 'id' e 'text'
            contract_id: ID do contrato

        Returns:
            Lista de resultados de descoberta
        """
        results = []

        for clause in clauses:
            text = clause.get("text", "")
            if text:
                result = self.analyze_text(text)
                results.append(result)

        return results

    def suggest_predicate_for_clause(
        self,
        clause_text: str,
        top_k: int = 5
    ) -> list[tuple[DynamicPredicate, float]]:
        """
        Sugere predicados existentes relevantes para uma cláusula.

        Args:
            clause_text: Texto da cláusula
            top_k: Número máximo de sugestões

        Returns:
            Lista de (predicado, score de relevância)
        """
        suggestions = self.ontology.suggest_predicates(clause_text)

        # Calcular score mais refinado
        scored = []
        text_lower = clause_text.lower()

        for pred in suggestions:
            score = 0.0

            # Score por nome do predicado no texto
            if pred.name.lower() in text_lower:
                score += 0.5

            # Score por palavras da descrição
            desc_words = pred.description.lower().split()
            for word in desc_words:
                if len(word) > 3 and word in text_lower:
                    score += 0.1

            # Score por exemplos similares
            for example in pred.examples:
                example_words = set(re.findall(r"\w+", example.lower()))
                text_words = set(re.findall(r"\w+", text_lower))
                overlap = len(example_words & text_words)
                score += overlap * 0.05

            # Boost por uso frequente
            score += min(pred.metadata.usage_count * 0.01, 0.2)

            scored.append((pred, score))

        # Ordenar por score e retornar top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_coverage_report(self, clauses: list[dict]) -> dict[str, Any]:
        """
        Gera relatório de cobertura da ontologia para cláusulas.

        Args:
            clauses: Lista de cláusulas com 'text'

        Returns:
            Relatório de cobertura
        """
        total_clauses = len(clauses)
        covered_clauses = 0
        uncovered_concepts_all = []
        predicate_usage = {}

        for clause in clauses:
            text = clause.get("text", "")
            if not text:
                continue

            uncovered = self._identify_uncovered_concepts(text)
            coverage = self._check_existing_coverage(text)

            if coverage and not uncovered:
                covered_clauses += 1

            for pred in coverage:
                predicate_usage[pred] = predicate_usage.get(pred, 0) + 1

            for concept, _ in uncovered:
                uncovered_concepts_all.append(concept)

        # Contar conceitos não cobertos
        concept_counts = {}
        for concept in uncovered_concepts_all:
            concept_counts[concept] = concept_counts.get(concept, 0) + 1

        return {
            "total_clauses": total_clauses,
            "covered_clauses": covered_clauses,
            "coverage_rate": covered_clauses / total_clauses if total_clauses > 0 else 0.0,
            "predicate_usage": predicate_usage,
            "uncovered_concepts": concept_counts,
            "recommended_new_predicates": [
                c for c, count in concept_counts.items() if count >= 2
            ],
        }


def discover_predicates(
    text: str,
    llm_client: Any | None = None,
    auto_register: bool = False
) -> DiscoveryResult:
    """
    Função utilitária para descoberta de predicados.

    Args:
        text: Texto para análise
        llm_client: Cliente LLM (opcional)
        auto_register: Se True, registra predicados automaticamente

    Returns:
        Resultado da descoberta
    """
    discoverer = PredicateDiscovery(
        llm_client=llm_client,
        auto_register=auto_register,
    )
    return discoverer.analyze_text(text)
