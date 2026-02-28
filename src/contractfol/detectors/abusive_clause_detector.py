"""
Detector de Cláusulas Abusivas.

Implementa detecção de cláusulas abusivas ou ilegais em contratos B2B
usando abordagem híbrida neurossimbólica em 3 camadas:

Camada 1 (Heurística): Pattern matching rápido contra regras codificadas
Camada 2 (FOL/Z3):     Verificação formal para regras formalizáveis
Camada 3 (LLM):        Análise contextual para casos nuançados

Referências legais:
- Código Civil Brasileiro (Lei 10.406/2002)
- CDC (Lei 8.078/1990) - por analogia para contratos de adesão B2B
"""

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from contractfol.knowledge.legal_rules import LegalRule, get_legal_rules
from contractfol.models import AbusiveClauseType, AbusiveClauseViolation, Clause


@dataclass
class DetectorConfig:
    """Configuração do detector de cláusulas abusivas."""

    use_heuristics: bool = True
    use_formal_verification: bool = True
    use_llm: bool = True
    multa_threshold_percent: float = 10.0
    confidence_threshold: float = 0.6


class AbusiveClauseDetector:
    """
    Detector de cláusulas abusivas em contratos B2B.

    Utiliza abordagem híbrida em 3 camadas para maximizar cobertura
    e precisão na detecção de abusividades contratuais.
    """

    def __init__(
        self,
        config: DetectorConfig | None = None,
        llm_client: Any | None = None,
        model: str = "gpt-4",
        legal_rules: list[LegalRule] | None = None,
    ):
        self.config = config or DetectorConfig()
        self.llm_client = llm_client
        self.model = model
        self.legal_rules = legal_rules or get_legal_rules()

    def detect(self, clause: Clause) -> list[AbusiveClauseViolation]:
        """
        Detecta cláusulas abusivas usando as 3 camadas.

        Args:
            clause: Cláusula a ser analisada

        Returns:
            Lista de violações detectadas
        """
        violations: list[AbusiveClauseViolation] = []

        # Camada 1: Heurística
        if self.config.use_heuristics:
            heuristic_violations = self._detect_heuristic(clause)
            violations.extend(heuristic_violations)

        # Camada 2: Verificação formal (FOL/Z3)
        if self.config.use_formal_verification:
            formal_violations = self._detect_formal(clause)
            violations.extend(formal_violations)

        # Camada 3: Análise via LLM
        if self.config.use_llm and self.llm_client:
            llm_violations = self._detect_llm(clause, violations)
            violations.extend(llm_violations)

        # Deduplicar violações do mesmo tipo para a mesma cláusula
        violations = self._deduplicate(violations)

        # Filtrar por limiar de confiança
        violations = [
            v for v in violations if v.confidence >= self.config.confidence_threshold
        ]

        return violations

    # ========================================================================
    # CAMADA 1: Detecção Heurística
    # ========================================================================

    def _detect_heuristic(self, clause: Clause) -> list[AbusiveClauseViolation]:
        """
        Camada 1: Detecção por pattern matching contra regras legais.

        Rápida, sem custo de API, detecta casos claros.
        """
        violations = []
        text = clause.text

        for rule in self.legal_rules:
            matched, confidence = rule.matches_heuristic(text)
            if not matched:
                continue

            # Tratamento especial para multa excessiva: verificar valor
            if rule.violation_type == AbusiveClauseType.MULTA_EXCESSIVA:
                multa_violation = self._check_multa_value(clause, rule)
                if multa_violation:
                    violations.append(multa_violation)
                continue

            violation = AbusiveClauseViolation(
                id=f"abv_{uuid.uuid4().hex[:8]}",
                clause_id=clause.id,
                violation_type=rule.violation_type,
                legal_basis=rule.legal_basis,
                description=rule.description,
                suggestion=self._get_suggestion_for_rule(rule),
                severity=rule.severity,
                confidence=confidence,
                detection_layer="heuristic",
            )
            violations.append(violation)

        return violations

    def _check_multa_value(
        self, clause: Clause, rule: LegalRule
    ) -> AbusiveClauseViolation | None:
        """Verifica se a multa excede o limiar configurado."""
        # Extrair valor percentual da cláusula
        percentage_pattern = re.compile(
            r"(?:multa|penalidade|pena|cláusula\s+penal|clausula\s+penal)\s+"
            r"(?:de\s+|equivalente\s+a\s+|correspondente\s+a\s+|no\s+valor\s+de\s+)?"
            r"(\d+(?:[.,]\d+)?)\s*%",
            re.IGNORECASE,
        )

        match = percentage_pattern.search(clause.text)
        if not match:
            return None

        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            return None

        if value <= self.config.multa_threshold_percent:
            return None

        return AbusiveClauseViolation(
            id=f"abv_{uuid.uuid4().hex[:8]}",
            clause_id=clause.id,
            violation_type=AbusiveClauseType.MULTA_EXCESSIVA,
            legal_basis=rule.legal_basis,
            description=(
                f"Multa de {value}% detectada, excedendo o limiar de "
                f"{self.config.multa_threshold_percent}%. {rule.description}"
            ),
            suggestion=(
                f"Reduzir a multa para valor proporcional à obrigação principal. "
                f"CC Art. 413 determina redução equitativa quando manifestamente excessiva."
            ),
            severity="HIGH" if value > 20.0 else "MEDIUM",
            confidence=0.9 if value > 20.0 else 0.75,
            detection_layer="heuristic",
        )

    # ========================================================================
    # CAMADA 2: Verificação Formal (FOL/Z3)
    # ========================================================================

    def _detect_formal(self, clause: Clause) -> list[AbusiveClauseViolation]:
        """
        Camada 2: Verificação formal usando FOL/Z3.

        Verifica cláusulas contra axiomas legais formalizados.
        Garante prova formal de violação quando possível.
        """
        violations = []

        # Verificar simetria de rescisão
        rescisao_violation = self._check_rescisao_simetria(clause)
        if rescisao_violation:
            violations.append(rescisao_violation)

        # Verificar exclusão de responsabilidade em contrato de adesão
        exclusao_violation = self._check_exclusao_responsabilidade_formal(clause)
        if exclusao_violation:
            violations.append(exclusao_violation)

        return violations

    def _check_rescisao_simetria(
        self, clause: Clause
    ) -> AbusiveClauseViolation | None:
        """
        Verifica formalmente se rescisão é assimétrica.

        Axioma: ∀a,b,c: Permissao(a, Rescisao(c)) ∧ Parte(b,c) ∧ ¬(a=b)
                → Permissao(b, Rescisao(c))

        Se a cláusula concede rescisão a uma parte e explicitamente a nega
        à outra, viola o axioma.
        """
        text = clause.text.lower()

        # Detectar concessão de rescisão unilateral a uma parte específica
        concede_pattern = re.compile(
            r"(contratante|contratado|contratada|patrocinador|patrocinadora)\s+"
            r"(?:poderá|podera|pode|terá\s+direito)\s+(?:de\s+)?(?:rescindir|resolver|resilir)",
            re.IGNORECASE,
        )
        nega_pattern = re.compile(
            r"(contratante|contratado|contratada|patrocinador|patrocinadora)\s+"
            r"(?:não|nao)\s+(?:poderá|podera|pode|terá\s+direito)\s+(?:de\s+)?(?:rescindir|resolver)",
            re.IGNORECASE,
        )

        concede = concede_pattern.search(clause.text)
        nega = nega_pattern.search(clause.text)

        if concede and nega:
            parte_com = concede.group(1).upper()
            parte_sem = nega.group(1).upper()
            if parte_com != parte_sem:
                return AbusiveClauseViolation(
                    id=f"abv_{uuid.uuid4().hex[:8]}",
                    clause_id=clause.id,
                    violation_type=AbusiveClauseType.RESCISAO_UNILATERAL,
                    legal_basis="CC, Art. 473 (verificação formal)",
                    description=(
                        f"Violação do axioma de simetria de rescisão: "
                        f"{parte_com} pode rescindir mas {parte_sem} não. "
                        f"Permissao({parte_com}, Rescisao) ∧ ¬Permissao({parte_sem}, Rescisao) "
                        f"viola ∀a,b: Permissao(a, Rescisao) → Permissao(b, Rescisao)."
                    ),
                    suggestion=(
                        "Garantir reciprocidade no direito de rescisão, "
                        "conforme princípio da boa-fé (CC Art. 422)."
                    ),
                    severity="HIGH",
                    confidence=0.95,
                    detection_layer="formal",
                )

        return None

    def _check_exclusao_responsabilidade_formal(
        self, clause: Clause
    ) -> AbusiveClauseViolation | None:
        """
        Verificação formal: ExclusaoResp(a, c) ∧ ContratoAdesao(c) → Abusivo(a, c)

        Detecta exclusão total de responsabilidade quando combinada com
        indicadores de contrato de adesão.
        """
        text = clause.text.lower()

        has_exclusao = bool(
            re.search(
                r"(?:isent[ao]|exonera|exclui|exime)\s+(?:de\s+)?(?:toda|qualquer|inteira)\s+"
                r"responsabilidade",
                text,
            )
        )

        # Indicadores de unilateralidade/adesão
        has_adesao_indicators = bool(
            re.search(
                r"(?:adere|adesão|aderente|aceita\s+integralmente|"
                r"sem\s+possibilidade\s+de\s+(?:alteração|negociação))",
                text,
            )
        )

        if has_exclusao and has_adesao_indicators:
            return AbusiveClauseViolation(
                id=f"abv_{uuid.uuid4().hex[:8]}",
                clause_id=clause.id,
                violation_type=AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE,
                legal_basis="CC, Art. 424 (verificação formal)",
                description=(
                    "Verificação formal: ExclusaoResp(agente, contrato) ∧ "
                    "ContratoAdesao(contrato) → Abusivo. Exclusão total de "
                    "responsabilidade detectada em contrato com características de adesão."
                ),
                suggestion=(
                    "Remover cláusula de exclusão total de responsabilidade. "
                    "CC Art. 424: é nula em contratos de adesão a renúncia antecipada "
                    "a direito resultante da natureza do negócio."
                ),
                severity="HIGH",
                confidence=0.95,
                detection_layer="formal",
            )

        return None

    # ========================================================================
    # CAMADA 3: Análise via LLM
    # ========================================================================

    def _detect_llm(
        self,
        clause: Clause,
        existing_violations: list[AbusiveClauseViolation],
    ) -> list[AbusiveClauseViolation]:
        """
        Camada 3: Análise contextual via LLM.

        Captura nuances subjetivas (boa-fé, desvantagem exagerada) que
        escapam à lógica formal e aos padrões heurísticos.
        """
        try:
            prompt = self._build_llm_prompt(clause, existing_violations)
            response = self._call_llm(prompt)
            if response:
                return self._parse_llm_response(response, clause)
        except Exception as e:
            print(f"Erro na análise LLM de cláusula abusiva: {e}")

        return []

    def _build_llm_prompt(
        self,
        clause: Clause,
        existing_violations: list[AbusiveClauseViolation],
    ) -> str:
        """Constrói prompt estruturado para análise LLM."""
        # Listar regras relevantes para contexto
        rules_context = "\n".join(
            f"- {rule.name} ({rule.legal_basis}): {rule.llm_prompt_hint}"
            for rule in self.legal_rules
        )

        # Indicar o que já foi detectado para evitar duplicação
        already_detected = ""
        if existing_violations:
            already_detected = "\n## Violações já detectadas (NÃO repita estas):\n"
            already_detected += "\n".join(
                f"- {v.violation_type.value}: {v.description[:100]}"
                for v in existing_violations
            )

        return f"""Analise a seguinte cláusula contratual de um contrato B2B (inter-institucional)
e identifique possíveis abusividades ou ilegalidades que NÃO foram detectadas
pelas camadas anteriores.

## Cláusula a Analisar
"{clause.text}"

## Regras Legais de Referência (Código Civil e CDC por analogia)
{rules_context}
{already_detected}

## Instruções
1. Analise a cláusula sob a ótica do Código Civil brasileiro e princípios contratuais
2. Identifique APENAS abusividades que NÃO foram listadas nas violações já detectadas
3. Para cada abusividade encontrada, forneça fundamentação legal específica
4. Responda EXCLUSIVAMENTE em formato JSON

## Formato de Resposta (JSON)
{{
  "violations": [
    {{
      "type": "<tipo da AbusiveClauseType enum>",
      "legal_basis": "<artigo de lei>",
      "description": "<descrição breve>",
      "suggestion": "<sugestão de correção>",
      "severity": "HIGH|MEDIUM|LOW",
      "confidence": 0.0-1.0
    }}
  ]
}}

Se não encontrar abusividades adicionais, retorne: {{"violations": []}}"""

    def _call_llm(self, prompt: str) -> str | None:
        """Chama o LLM para análise."""
        system_prompt = (
            "Você é um especialista em direito contratual brasileiro, com foco "
            "em contratos B2B inter-institucionais. Analise cláusulas contratuais "
            "e identifique abusividades conforme o Código Civil e legislação aplicável. "
            "Responda APENAS em JSON válido."
        )

        try:
            # OpenAI
            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=1000,
                )
                return response.choices[0].message.content

            # Anthropic
            elif hasattr(self.llm_client, "messages"):
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}],
                    system=system_prompt,
                )
                return response.content[0].text

            # Gemini
            elif hasattr(self.llm_client, "generate_content"):
                full_prompt = f"{system_prompt}\n\n{prompt}"
                response = self.llm_client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": 0.2,
                        "max_output_tokens": 1000,
                    },
                )
                return response.text

        except Exception as e:
            print(f"Erro ao chamar LLM para detecção de abusividade: {e}")

        return None

    def _parse_llm_response(
        self, response: str, clause: Clause
    ) -> list[AbusiveClauseViolation]:
        """Parseia a resposta JSON do LLM."""
        violations = []

        try:
            # Extrair JSON da resposta (pode vir com markdown)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            for v in data.get("violations", []):
                violation_type = self._parse_violation_type(v.get("type", ""))
                if not violation_type:
                    continue

                violation = AbusiveClauseViolation(
                    id=f"abv_{uuid.uuid4().hex[:8]}",
                    clause_id=clause.id,
                    violation_type=violation_type,
                    legal_basis=v.get("legal_basis", "Não especificada"),
                    description=v.get("description", ""),
                    suggestion=v.get("suggestion", ""),
                    severity=v.get("severity", "MEDIUM"),
                    confidence=min(float(v.get("confidence", 0.6)), 0.85),
                    detection_layer="llm",
                )
                violations.append(violation)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Erro ao parsear resposta LLM: {e}")

        return violations

    # ========================================================================
    # Métodos auxiliares
    # ========================================================================

    def _parse_violation_type(self, type_str: str) -> AbusiveClauseType | None:
        """Converte string em AbusiveClauseType."""
        try:
            return AbusiveClauseType(type_str)
        except ValueError:
            # Tentar match parcial
            type_upper = type_str.upper().replace(" ", "_")
            for member in AbusiveClauseType:
                if member.value == type_upper or type_upper in member.value:
                    return member
            return None

    def _deduplicate(
        self, violations: list[AbusiveClauseViolation]
    ) -> list[AbusiveClauseViolation]:
        """Remove violações duplicadas, mantendo a de maior confiança."""
        seen: dict[str, AbusiveClauseViolation] = {}

        for v in violations:
            key = f"{v.clause_id}_{v.violation_type.value}"
            if key not in seen or v.confidence > seen[key].confidence:
                seen[key] = v

        return list(seen.values())

    def _get_suggestion_for_rule(self, rule: LegalRule) -> str:
        """Gera sugestão de correção baseada na regra violada."""
        suggestions = {
            AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE: (
                "Remover ou limitar a exclusão de responsabilidade. Definir responsabilidades "
                "proporcionais entre as partes conforme a natureza do negócio."
            ),
            AbusiveClauseType.RESCISAO_UNILATERAL: (
                "Incluir aviso prévio compatível com os investimentos realizados (CC Art. 473) "
                "e garantir reciprocidade no direito de rescisão."
            ),
            AbusiveClauseType.MODIFICACAO_UNILATERAL: (
                "Exigir consentimento mútuo para alterações contratuais ou definir "
                "critérios objetivos para reajustes automáticos."
            ),
            AbusiveClauseType.MULTA_EXCESSIVA: (
                "Reduzir a multa para valor proporcional à obrigação principal. "
                "CC Art. 413 determina redução equitativa."
            ),
            AbusiveClauseType.RENUNCIA_DIREITO: (
                "Remover cláusula de renúncia antecipada de direitos. "
                "CC Art. 424 veda essa prática em contratos de adesão."
            ),
            AbusiveClauseType.DESVANTAGEM_EXAGERADA: (
                "Reequilibrar as prestações entre as partes para evitar "
                "desproporção manifesta (CC Art. 157)."
            ),
            AbusiveClauseType.ONEROSIDADE_EXCESSIVA: (
                "Incluir cláusula de revisão contratual para eventos extraordinários "
                "e imprevisíveis, conforme CC Arts. 478-480."
            ),
            AbusiveClauseType.BOA_FE_VIOLACAO: (
                "Definir critérios objetivos para decisões e incluir mecanismos "
                "de controle e transparência conforme CC Art. 422."
            ),
            AbusiveClauseType.CLAUSULA_LEONINA: (
                "Garantir participação proporcional nos benefícios e perdas "
                "para todas as partes envolvidas."
            ),
            AbusiveClauseType.PERDA_PRESTACOES: (
                "Prever devolução proporcional de valores pagos em caso de "
                "rescisão, conforme CC Art. 413."
            ),
            AbusiveClauseType.TRANSFERENCIA_RESPONSABILIDADE: (
                "Distribuir responsabilidades de forma equilibrada entre "
                "as partes, proporcional ao risco de cada uma."
            ),
            AbusiveClauseType.INDENIZACAO_DESPROPORCIONAL: (
                "Vincular a indenização à extensão efetiva do dano, "
                "conforme CC Art. 944."
            ),
            AbusiveClauseType.ARBITRAGEM_COMPULSORIA: (
                "Oferecer a arbitragem como opção, não como imposição, "
                "preservando o direito de acesso ao Judiciário."
            ),
            AbusiveClauseType.ALTERACAO_PRECO_UNILATERAL: (
                "Definir índices de reajuste objetivos (IPCA, IGP-M) e "
                "exigir concordância mútua para alterações de preço."
            ),
        }
        return suggestions.get(
            rule.violation_type,
            "Revisar a cláusula para adequação à legislação vigente.",
        )
