"""
Classificador Deôntico de Cláusulas Contratuais.

Implementa a classificação de cláusulas em modalidades deônticas conforme
Seção 5.4 da dissertação:
- OBRIGACAO_ATIVA: Agente deve fazer algo
- OBRIGACAO_PASSIVA: Agente deve permitir algo
- PERMISSAO: Agente pode fazer algo
- PROIBICAO: Agente não pode fazer algo
- CONDICAO: Cláusula condicional
- DEFINICAO: Cláusula definitória

O classificador utiliza LLMs com prompting estruturado e pode ser
complementado com um modelo Legal-BERT fine-tuned.
"""

import json
import re
from typing import Any

from contractfol.models import Clause, DeonticModality


# Padrões heurísticos para classificação inicial
DEONTIC_PATTERNS = {
    DeonticModality.OBRIGACAO_ATIVA: [
        r"\b(obriga-se|obrigará|deverá|deve|compromete-se|fica\s+obrigad[oa]|"
        r"responsabiliza-se|arcará\s+com|pagará|entregará|realizará|"
        r"providenciará|executará|cumprirá|disponibilizará|fornecerá)\b",
        r"\b(é\s+de\s+responsabilidade|cabe\s+a[o]?|incumbe|compete)\b",
    ],
    DeonticModality.OBRIGACAO_PASSIVA: [
        r"\b(deverá\s+permitir|deverá\s+aceitar|deverá\s+tolerar|"
        r"não\s+poderá\s+impedir|não\s+poderá\s+obstar)\b",
    ],
    DeonticModality.PERMISSAO: [
        r"\b(poderá|pode|é\s+permitido|é\s+facultad[oa]|tem\s+direito|"
        r"fica\s+autorizad[oa]|está\s+autorizad[oa]|é\s+lícito)\b",
        r"\b(terá\s+direito|faz\s+jus|gozará|usufruirá)\b",
    ],
    DeonticModality.PROIBICAO: [
        r"\b(não\s+poderá|não\s+pode|é\s+proibid[oa]|é\s+vedad[oa]|"
        r"fica\s+proibid[oa]|fica\s+vedad[oa]|não\s+deverá|"
        r"é\s+defeso|não\s+é\s+permitido|não\s+será\s+permitido)\b",
        r"\b(abster-se-á|deverá\s+abster-se|compromete-se\s+a\s+não)\b",
    ],
    DeonticModality.CONDICAO: [
        r"\b(caso|se|quando|desde\s+que|na\s+hipótese|em\s+caso\s+de|"
        r"verificando-se|ocorrendo|havendo|mediante|sob\s+condição)\b",
        r"\b(então|acarretará|ensejará|implicará|resultará)\b",
    ],
    DeonticModality.DEFINICAO: [
        r"\b(entende-se\s+por|considera-se|para\s+(os\s+)?efeitos?\s+(deste|desta)|"
        r"define-se|significa|refere-se\s+a|compreende)\b",
        r"\b(são\s+partes|celebram\s+o\s+presente|as\s+partes\s+abaixo)\b",
    ],
}


class DeonticClassifier:
    """
    Classificador de modalidades deônticas.

    Implementa classificação híbrida:
    1. Heurísticas baseadas em padrões de regex (rápida, alta recall)
    2. LLM para classificação mais precisa (quando disponível)
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        model: str = "gpt-4",
        use_heuristics: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Inicializa o classificador.

        Args:
            llm_client: Cliente OpenAI/Anthropic (opcional)
            model: Nome do modelo LLM a utilizar
            use_heuristics: Se deve usar heurísticas além do LLM
            confidence_threshold: Limiar mínimo de confiança
        """
        self.llm_client = llm_client
        self.model = model
        self.use_heuristics = use_heuristics
        self.confidence_threshold = confidence_threshold

        # Compilar padrões
        self._compiled_patterns: dict[DeonticModality, list[re.Pattern]] = {}
        for modality, patterns in DEONTIC_PATTERNS.items():
            self._compiled_patterns[modality] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify(self, clause: Clause) -> tuple[DeonticModality, float]:
        """
        Classifica uma cláusula em uma modalidade deôntica.

        Args:
            clause: Objeto Clause a ser classificado

        Returns:
            Tupla (modalidade, confiança)
        """
        text = clause.text

        # Primeira tentativa: heurísticas
        if self.use_heuristics:
            modality, confidence = self._classify_heuristic(text)
            if confidence >= self.confidence_threshold:
                return modality, confidence

        # Segunda tentativa: LLM (se disponível)
        if self.llm_client:
            return self._classify_llm(text)

        # Fallback para heurísticas mesmo com baixa confiança
        return self._classify_heuristic(text)

    def classify_batch(self, clauses: list[Clause]) -> list[tuple[DeonticModality, float]]:
        """Classifica múltiplas cláusulas."""
        return [self.classify(clause) for clause in clauses]

    def _classify_heuristic(self, text: str) -> tuple[DeonticModality, float]:
        """
        Classificação baseada em heurísticas de regex.

        Returns:
            Tupla (modalidade, confiança baseada em matches)
        """
        scores: dict[DeonticModality, int] = {m: 0 for m in DeonticModality}

        for modality, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                scores[modality] += len(matches)

        # Encontrar modalidade com maior score
        total_matches = sum(scores.values())
        if total_matches == 0:
            return DeonticModality.DEFINICAO, 0.3  # Default com baixa confiança

        best_modality = max(scores, key=scores.get)
        confidence = scores[best_modality] / total_matches

        # Ajustar confiança baseado no número total de matches
        if total_matches >= 3:
            confidence = min(confidence + 0.1, 0.95)

        return best_modality, confidence

    def _classify_llm(self, text: str) -> tuple[DeonticModality, float]:
        """
        Classificação usando LLM.

        Returns:
            Tupla (modalidade, confiança)
        """
        prompt = self._build_classification_prompt(text)

        try:
            if hasattr(self.llm_client, "chat") and hasattr(self.llm_client.chat, "completions"):
                # OpenAI-style client
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
                result_text = response.choices[0].message.content
            elif hasattr(self.llm_client, "messages"):
                # Anthropic-style client
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                    system=self._get_system_prompt(),
                )
                result_text = response.content[0].text
            else:
                raise ValueError("Cliente LLM não reconhecido")

            return self._parse_llm_response(result_text)

        except Exception as e:
            # Fallback para heurísticas em caso de erro
            print(f"Erro na classificação LLM: {e}")
            return self._classify_heuristic(text)

    def _get_system_prompt(self) -> str:
        """Retorna o prompt de sistema para classificação."""
        return """Você é um especialista em análise jurídica de contratos brasileiros.
Sua tarefa é classificar cláusulas contratuais em modalidades deônticas.

As modalidades disponíveis são:
- OBRIGACAO_ATIVA: O agente deve realizar uma ação (obriga-se a fazer algo)
- OBRIGACAO_PASSIVA: O agente deve permitir ou tolerar algo
- PERMISSAO: O agente tem permissão para fazer algo (pode, é facultado)
- PROIBICAO: O agente é proibido de fazer algo (não pode, é vedado)
- CONDICAO: Cláusula que estabelece uma condição (se... então)
- DEFINICAO: Cláusula definitória ou identificação das partes

Responda APENAS com um JSON no formato:
{"modalidade": "NOME_DA_MODALIDADE", "confianca": 0.XX, "justificativa": "breve explicação"}"""

    def _build_classification_prompt(self, text: str) -> str:
        """Constrói o prompt para classificação de uma cláusula."""
        # Truncar texto se muito longo
        max_length = 1500
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return f"""Classifique a seguinte cláusula contratual:

---
{text}
---

Identifique a modalidade deôntica principal desta cláusula."""

    def _parse_llm_response(self, response: str) -> tuple[DeonticModality, float]:
        """Faz parse da resposta do LLM."""
        try:
            # Tentar extrair JSON da resposta
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                data = json.loads(json_match.group())
                modality_str = data.get("modalidade", "DEFINICAO").upper()
                confidence = float(data.get("confianca", 0.7))

                # Converter string para enum
                try:
                    modality = DeonticModality[modality_str]
                except KeyError:
                    modality = DeonticModality.DEFINICAO

                return modality, confidence

        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: tentar identificar modalidade no texto
        response_upper = response.upper()
        for modality in DeonticModality:
            if modality.value in response_upper:
                return modality, 0.6

        return DeonticModality.DEFINICAO, 0.4

    def update_clause(self, clause: Clause) -> Clause:
        """
        Classifica e atualiza o objeto Clause com a modalidade.

        Args:
            clause: Cláusula a ser classificada

        Returns:
            Cláusula atualizada com modalidade e confiança
        """
        modality, confidence = self.classify(clause)
        clause.modality = modality
        clause.modality_confidence = confidence
        return clause


def classify_clauses(clauses: list[Clause], llm_client: Any = None) -> list[Clause]:
    """
    Função utilitária para classificar múltiplas cláusulas.

    Args:
        clauses: Lista de cláusulas
        llm_client: Cliente LLM opcional

    Returns:
        Lista de cláusulas com modalidades classificadas
    """
    classifier = DeonticClassifier(llm_client=llm_client)
    return [classifier.update_clause(clause) for clause in clauses]
