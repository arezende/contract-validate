"""
Gerador de Explicações em Linguagem Natural.

Implementa a geração de explicações compreensíveis para usuários não
especialistas em lógica, conforme Seção 5.7 da dissertação.

O processo:
1. Identifica as cláusulas originais envolvidas no conflito
2. Utiliza templates para explicar o tipo de conflito
3. Gera sugestões de resolução baseadas no tipo de inconsistência

Exemplo de Explicação Gerada (da dissertação):
---
CONFLITO DETECTADO entre Cláusula 3.2 e Cláusula 7.1:
A Cláusula 3.2 proíbe o CONTRATADO de utilizar a marca do COB sem
autorização prévia. A Cláusula 7.1 obriga o CONTRATADO a exibir a marca
em materiais promocionais.
SUGESTÃO: Adicionar ressalva na Cláusula 3.2 excluindo uso autorizado
para materiais promocionais conforme Cláusula 7.1.
---
"""

import json
from dataclasses import dataclass
from typing import Any

from contractfol.models import Clause, Conflict, ConflictType, ValidationReport


# Templates de explicação para cada tipo de conflito
CONFLICT_TEMPLATES = {
    ConflictType.OBRIGACAO_PROIBICAO: {
        "title": "Conflito entre Obrigação e Proibição",
        "description": (
            "Foi detectado um conflito lógico: uma cláusula obriga a realizar "
            "uma ação que outra cláusula proíbe expressamente."
        ),
        "template": (
            "A {clause1_ref} {clause1_action}. "
            "Porém, a {clause2_ref} {clause2_action}. "
            "Essas disposições são logicamente incompatíveis."
        ),
        "suggestion_template": (
            "SUGESTÃO: {suggestion_action} para harmonizar as disposições contratuais."
        ),
        "default_suggestions": [
            "Revisar as cláusulas para definir claramente as exceções aplicáveis",
            "Adicionar cláusula de prevalência indicando qual disposição tem prioridade",
            "Especificar condições distintas para cada obrigação/proibição",
        ],
    },
    ConflictType.OBRIGACOES_MUTUAMENTE_EXCLUSIVAS: {
        "title": "Obrigações Mutuamente Exclusivas",
        "description": (
            "As cláusulas estabelecem obrigações que não podem ser cumpridas "
            "simultaneamente pelo mesmo agente."
        ),
        "template": (
            "A {clause1_ref} estabelece que {clause1_action}. "
            "A {clause2_ref} determina que {clause2_action}. "
            "O cumprimento de uma obrigação impossibilita o cumprimento da outra."
        ),
        "suggestion_template": (
            "SUGESTÃO: {suggestion_action}"
        ),
        "default_suggestions": [
            "Definir prioridade temporal entre as obrigações",
            "Estabelecer condições alternativas para cada obrigação",
            "Revisar os prazos para permitir cumprimento sequencial",
        ],
    },
    ConflictType.PRAZO_INCONSISTENTE: {
        "title": "Inconsistência de Prazos",
        "description": (
            "Os prazos estabelecidos nas cláusulas são contraditórios ou "
            "impossíveis de cumprir."
        ),
        "template": (
            "A {clause1_ref} define prazo de {clause1_action}. "
            "A {clause2_ref} estabelece prazo de {clause2_action}. "
            "Esses prazos são incompatíveis entre si."
        ),
        "suggestion_template": (
            "SUGESTÃO: {suggestion_action}"
        ),
        "default_suggestions": [
            "Harmonizar os prazos estabelecidos",
            "Definir uma cláusula de prevalência para conflitos de prazo",
            "Estabelecer prazo único que atenda ambas as disposições",
        ],
    },
    ConflictType.CONDICAO_IMPOSSIVEL: {
        "title": "Condição Impossível de Satisfazer",
        "description": (
            "As condições estabelecidas criam um ciclo lógico impossível "
            "ou são mutuamente excludentes."
        ),
        "template": (
            "As condições estabelecidas nas cláusulas {clause_refs} "
            "criam uma situação logicamente impossível de satisfazer."
        ),
        "suggestion_template": (
            "SUGESTÃO: Revisar a estrutura condicional das cláusulas para "
            "eliminar dependências circulares ou condições contraditórias."
        ),
        "default_suggestions": [
            "Simplificar a estrutura condicional",
            "Definir condições alternativas",
            "Remover condições redundantes ou contraditórias",
        ],
    },
    ConflictType.VALOR_INCONSISTENTE: {
        "title": "Valores Monetários Inconsistentes",
        "description": (
            "Os valores monetários especificados nas cláusulas são "
            "contraditórios ou inconsistentes."
        ),
        "template": (
            "A {clause1_ref} especifica valor de {clause1_action}. "
            "A {clause2_ref} indica valor de {clause2_action}. "
            "Há inconsistência entre os valores."
        ),
        "suggestion_template": (
            "SUGESTÃO: {suggestion_action}"
        ),
        "default_suggestions": [
            "Verificar e corrigir os valores especificados",
            "Definir qual cláusula prevalece em caso de divergência",
            "Adicionar cláusula de ajuste automático",
        ],
    },
}


@dataclass
class ExplanationResult:
    """Resultado da geração de explicação."""

    conflict_id: str
    title: str
    description: str
    detailed_explanation: str
    suggestions: list[str]
    affected_clauses: list[str]
    severity: str
    raw_data: dict


class ExplanationGenerator:
    """
    Gerador de explicações em linguagem natural para conflitos contratuais.
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        model: str = "gpt-4",
        use_templates: bool = True,
    ):
        """
        Inicializa o gerador.

        Args:
            llm_client: Cliente LLM para explicações avançadas (opcional)
            model: Nome do modelo LLM
            use_templates: Se deve usar templates (True) ou apenas LLM (False)
        """
        self.llm_client = llm_client
        self.model = model
        self.use_templates = use_templates

    def generate_explanation(
        self, conflict: Conflict, clauses: list[Clause]
    ) -> ExplanationResult:
        """
        Gera explicação para um conflito.

        Args:
            conflict: Objeto Conflict com informações do conflito
            clauses: Lista de todas as cláusulas para contexto

        Returns:
            ExplanationResult com explicação detalhada
        """
        # Obter cláusulas envolvidas no conflito
        conflict_clauses = [c for c in clauses if c.id in conflict.clause_ids]

        # Usar template base
        template = CONFLICT_TEMPLATES.get(
            conflict.conflict_type,
            CONFLICT_TEMPLATES[ConflictType.OBRIGACAO_PROIBICAO],
        )

        # Gerar explicação baseada em template
        explanation = self._generate_template_explanation(
            conflict, conflict_clauses, template
        )

        # Se LLM disponível, enriquecer explicação
        if self.llm_client:
            enriched = self._enrich_with_llm(conflict, conflict_clauses, explanation)
            if enriched:
                explanation = enriched

        return explanation

    def _generate_template_explanation(
        self, conflict: Conflict, clauses: list[Clause], template: dict
    ) -> ExplanationResult:
        """Gera explicação usando templates."""
        # Construir referências às cláusulas
        clause_refs = []
        clause_actions = []

        for clause in clauses:
            ref = f"Cláusula {clause.number}" if clause.number else f"Cláusula {clause.id}"
            clause_refs.append(ref)

            # Extrair ação principal da cláusula (simplificado)
            action = self._extract_action_summary(clause)
            clause_actions.append(action)

        # Construir explicação detalhada
        if len(clauses) >= 2:
            detailed = template["template"].format(
                clause1_ref=clause_refs[0],
                clause1_action=clause_actions[0],
                clause2_ref=clause_refs[1],
                clause2_action=clause_actions[1],
            )
        else:
            detailed = template["description"]

        # Sugestões
        suggestions = template.get("default_suggestions", [])
        if suggestions:
            suggestion_text = template["suggestion_template"].format(
                suggestion_action=suggestions[0]
            )
        else:
            suggestion_text = ""

        return ExplanationResult(
            conflict_id=conflict.id,
            title=template["title"],
            description=template["description"],
            detailed_explanation=f"{detailed}\n\n{suggestion_text}",
            suggestions=suggestions,
            affected_clauses=[c.id for c in clauses],
            severity=conflict.severity,
            raw_data={
                "conflict_type": conflict.conflict_type.value,
                "formulas": conflict.formulas,
                "unsat_core": conflict.unsat_core,
            },
        )

    def _extract_action_summary(self, clause: Clause) -> str:
        """Extrai um resumo da ação principal da cláusula."""
        text = clause.text
        modality = clause.modality

        # Limitar tamanho
        max_length = 200
        if len(text) > max_length:
            # Tentar encontrar um ponto de corte natural
            text = text[:max_length]
            last_period = text.rfind(".")
            if last_period > max_length // 2:
                text = text[: last_period + 1]
            else:
                text = text + "..."

        # Adicionar contexto da modalidade
        if modality:
            modality_desc = {
                "OBRIGACAO_ATIVA": "obriga",
                "OBRIGACAO_PASSIVA": "deve permitir",
                "PERMISSAO": "permite",
                "PROIBICAO": "proíbe",
                "CONDICAO": "estabelece condição",
                "DEFINICAO": "define",
            }
            prefix = modality_desc.get(modality.value, "estabelece")
            return f"{prefix}: \"{text}\""

        return f"\"{text}\""

    def _enrich_with_llm(
        self, conflict: Conflict, clauses: list[Clause], base_explanation: ExplanationResult
    ) -> ExplanationResult | None:
        """Enriquece a explicação usando LLM."""
        try:
            prompt = self._build_enrichment_prompt(conflict, clauses, base_explanation)

            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )
                result_text = response.choices[0].message.content
            elif hasattr(self.llm_client, "messages"):
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                    system=self._get_system_prompt(),
                )
                result_text = response.content[0].text
            else:
                return None

            # Parse da resposta
            return self._parse_llm_enrichment(result_text, base_explanation)

        except Exception as e:
            print(f"Erro ao enriquecer explicação com LLM: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """Prompt de sistema para enriquecimento."""
        return """Você é um especialista jurídico que explica conflitos contratuais
de forma clara e acessível para não-especialistas.

Sua tarefa é:
1. Explicar o conflito de forma simples e direta
2. Dar exemplos práticos das consequências
3. Sugerir formas de resolver o conflito

Use linguagem clara, evite jargões técnicos, e seja objetivo."""

    def _build_enrichment_prompt(
        self, conflict: Conflict, clauses: list[Clause], base: ExplanationResult
    ) -> str:
        """Constrói prompt para enriquecimento."""
        clauses_text = "\n\n".join(
            f"**Cláusula {c.number or c.id}:**\n{c.text}" for c in clauses
        )

        return f"""Analise o seguinte conflito contratual e forneça uma explicação
detalhada e sugestões de resolução.

## Tipo de Conflito
{base.title}

## Cláusulas Envolvidas
{clauses_text}

## Explicação Base
{base.detailed_explanation}

## Tarefa
1. Explique o conflito em termos práticos (o que aconteceria na prática)
2. Liste 3 sugestões concretas para resolver o conflito
3. Indique qual parte do contrato precisaria ser alterada

Responda em formato estruturado."""

    def _parse_llm_enrichment(
        self, response: str, base: ExplanationResult
    ) -> ExplanationResult:
        """Parse da resposta do LLM."""
        # Usar a resposta como explicação detalhada enriquecida
        enriched = ExplanationResult(
            conflict_id=base.conflict_id,
            title=base.title,
            description=base.description,
            detailed_explanation=response,
            suggestions=base.suggestions,
            affected_clauses=base.affected_clauses,
            severity=base.severity,
            raw_data=base.raw_data,
        )

        # Tentar extrair sugestões da resposta
        if "sugest" in response.lower():
            lines = response.split("\n")
            suggestions = []
            for line in lines:
                line = line.strip()
                if line and (
                    line.startswith("-")
                    or line.startswith("*")
                    or line.startswith("1")
                    or line.startswith("2")
                    or line.startswith("3")
                ):
                    suggestions.append(line.lstrip("-*0123456789. "))

            if suggestions:
                enriched.suggestions = suggestions[:5]

        return enriched

    def generate_report(
        self, validation_report: ValidationReport, clauses: list[Clause]
    ) -> str:
        """
        Gera relatório completo de validação.

        Args:
            validation_report: Resultado da validação
            clauses: Lista de cláusulas

        Returns:
            Relatório formatado em texto
        """
        lines = [
            "=" * 60,
            "RELATÓRIO DE VALIDAÇÃO CONTRATUAL - ContractFOL",
            "=" * 60,
            "",
            f"Contratos analisados: {', '.join(validation_report.contract_ids)}",
            f"Total de cláusulas: {validation_report.total_clauses}",
            f"Cláusulas traduzidas: {validation_report.clauses_translated}",
            f"Taxa de sucesso: {validation_report.translation_success_rate:.1%}",
            "",
            f"Status: {validation_report.status.value}",
            f"Conflitos detectados: {validation_report.conflict_count}",
            "",
        ]

        if validation_report.has_conflicts:
            lines.append("-" * 60)
            lines.append("CONFLITOS DETECTADOS")
            lines.append("-" * 60)

            for conflict in validation_report.conflicts:
                explanation = self.generate_explanation(conflict, clauses)

                lines.extend(
                    [
                        "",
                        f"### {explanation.title} ###",
                        f"Severidade: {explanation.severity}",
                        f"Cláusulas afetadas: {', '.join(explanation.affected_clauses)}",
                        "",
                        explanation.detailed_explanation,
                        "",
                        "Sugestões de resolução:",
                    ]
                )

                for i, sug in enumerate(explanation.suggestions, 1):
                    lines.append(f"  {i}. {sug}")

                lines.append("")

        else:
            lines.extend(
                [
                    "-" * 60,
                    "NENHUM CONFLITO DETECTADO",
                    "-" * 60,
                    "",
                    "As cláusulas analisadas são logicamente consistentes.",
                    "",
                ]
            )

        # Estatísticas de tempo
        lines.extend(
            [
                "-" * 60,
                "ESTATÍSTICAS DE PROCESSAMENTO",
                "-" * 60,
                f"Tempo de extração: {validation_report.extraction_time_ms:.1f}ms",
                f"Tempo de classificação: {validation_report.classification_time_ms:.1f}ms",
                f"Tempo de tradução: {validation_report.translation_time_ms:.1f}ms",
                f"Tempo de verificação: {validation_report.verification_time_ms:.1f}ms",
                f"Tempo total: {validation_report.total_time_ms:.1f}ms",
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)


def generate_conflict_explanation(
    conflict: Conflict, clauses: list[Clause], llm_client: Any = None
) -> str:
    """
    Função utilitária para gerar explicação de um conflito.
    """
    generator = ExplanationGenerator(llm_client=llm_client)
    result = generator.generate_explanation(conflict, clauses)
    return result.detailed_explanation
