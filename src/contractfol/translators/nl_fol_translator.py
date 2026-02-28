"""
Tradutor NL-FOL (Linguagem Natural para Lógica de Primeira Ordem).

Implementa a tradução de cláusulas contratuais em português para fórmulas
em Lógica de Primeira Ordem, conforme Seção 5.5 da dissertação.

O tradutor utiliza:
- Prompting estruturado com LLMs (GPT-4, Claude ou Gemini)
- Mecanismo de auto-refinamento baseado em feedback de verificadores
- Ontologia de domínio para guiar a tradução

Exemplo de tradução (da dissertação):
Cláusula: "O PATROCINADOR obriga-se a realizar o pagamento das parcelas
          até o quinto dia útil de cada mês."
FOL: ∀m.Mes(m) → Obrigacao(patrocinador, Pagamento(parcelas), QuintoDiaUtil(m))
"""

import re
from dataclasses import dataclass
from typing import Any

from contractfol.models import Clause, DeonticModality, FOLFormula
from contractfol.ontology import ContractOntology, get_ontology


@dataclass
class TranslationResult:
    """Resultado de uma tradução NL-FOL."""

    original_text: str
    fol_formula: str
    is_valid: bool
    validation_errors: list[str]
    attempts: int
    predicates_used: list[str]
    constants_used: list[str]


class FOLSyntaxValidator:
    """Validador de sintaxe FOL."""

    # Operadores e quantificadores válidos
    VALID_OPERATORS = {"∧", "∨", "→", "↔", "¬", "And", "Or", "Implies", "Not", "Iff", "->", "<->"}
    VALID_QUANTIFIERS = {"∀", "∃", "Forall", "Exists", "forall", "exists"}

    def __init__(self, ontology: ContractOntology | None = None):
        self.ontology = ontology or get_ontology()

    def validate(self, formula: str) -> tuple[bool, list[str]]:
        """
        Valida a sintaxe de uma fórmula FOL.

        Returns:
            Tupla (is_valid, list of errors)
        """
        errors = []

        # Verificar balanceamento de parênteses
        if not self._check_parentheses(formula):
            errors.append("Parênteses desbalanceados")

        # Verificar predicados conhecidos
        pred_valid, unknown_preds = self.ontology.validate_formula_predicates(formula)
        if not pred_valid:
            errors.append(f"Predicados desconhecidos: {', '.join(unknown_preds)}")

        # Verificar variáveis livres
        free_vars = self._find_free_variables(formula)
        if free_vars:
            errors.append(f"Variáveis potencialmente livres: {', '.join(free_vars)}")

        # Verificar sintaxe básica
        syntax_errors = self._check_basic_syntax(formula)
        errors.extend(syntax_errors)

        return len(errors) == 0, errors

    def _check_parentheses(self, formula: str) -> bool:
        """Verifica balanceamento de parênteses."""
        count = 0
        for char in formula:
            if char == "(":
                count += 1
            elif char == ")":
                count -= 1
            if count < 0:
                return False
        return count == 0

    def _find_free_variables(self, formula: str) -> list[str]:
        """Encontra variáveis potencialmente livres."""
        # Extrair variáveis quantificadas
        quantified = set()
        quant_pattern = r"(?:∀|∃|Forall|Exists|forall|exists)\s*([a-z][a-z0-9_]*)"
        for match in re.finditer(quant_pattern, formula, re.IGNORECASE):
            quantified.add(match.group(1).lower())

        # Extrair todas as variáveis usadas (minúsculas)
        var_pattern = r"\b([a-z][a-z0-9_]*)\b"
        all_vars = set(re.findall(var_pattern, formula))

        # Remover operadores e palavras reservadas
        reserved = {"and", "or", "not", "implies", "iff", "forall", "exists", "true", "false"}
        all_vars -= reserved

        # Extrair constantes: lowercase terms used as predicate arguments
        # (appear after '(' or ',' and before ',' or ')' within predicate calls)
        constants = set()
        const_pattern = r"(?<=[(,])\s*([a-z][a-z0-9_]*)\s*(?=[,)])"
        constants = set(re.findall(const_pattern, formula))
        all_vars -= constants

        # Variáveis livres são as que aparecem mas não estão quantificadas
        # (simplificação - não considera escopo)
        return list(all_vars - quantified)

    def _check_basic_syntax(self, formula: str) -> list[str]:
        """Verifica sintaxe básica."""
        errors = []

        # Verificar se não está vazia
        if not formula.strip():
            errors.append("Fórmula vazia")
            return errors

        # Verificar operadores mal formados
        if re.search(r"[∧∨→↔]{2,}", formula):
            errors.append("Operadores consecutivos sem operandos")

        # Verificar predicados mal formados (nome seguido de algo que não é parêntese)
        if re.search(r"\b[A-Z][a-zA-Z]*\s+[a-z]", formula):
            errors.append("Possível predicado sem parênteses de argumentos")

        return errors


class NLFOLTranslator:
    """
    Tradutor de Linguagem Natural para Lógica de Primeira Ordem.

    Implementa prompting estruturado com mecanismo de auto-refinamento.
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        model: str = "gpt-4",
        ontology: ContractOntology | None = None,
        max_refinement_attempts: int = 3,
    ):
        """
        Inicializa o tradutor.

        Args:
            llm_client: Cliente OpenAI, Anthropic ou Gemini
            model: Nome do modelo a utilizar
            ontology: Ontologia de domínio
            max_refinement_attempts: Máximo de tentativas de refinamento
        """
        self.llm_client = llm_client
        self.model = model
        self.ontology = ontology or get_ontology()
        self.max_refinement_attempts = max_refinement_attempts
        self.validator = FOLSyntaxValidator(self.ontology)

    def translate(
        self, clause: Clause, modality: DeonticModality | None = None
    ) -> TranslationResult:
        """
        Traduz uma cláusula para FOL.

        Args:
            clause: Cláusula a traduzir
            modality: Modalidade deôntica (opcional, pode usar a da cláusula)

        Returns:
            TranslationResult com a fórmula e metadados
        """
        modality = modality or clause.modality

        if not self.llm_client:
            # Modo fallback: usar heurísticas simples
            return self._translate_heuristic(clause, modality)

        # Tradução com LLM e auto-refinamento
        return self._translate_with_refinement(clause, modality)

    def _translate_with_refinement(
        self, clause: Clause, modality: DeonticModality | None
    ) -> TranslationResult:
        """
        Tradução com ciclo de auto-refinamento.

        O processo:
        1. Gerar tradução inicial
        2. Validar sintaxe
        3. Se inválida, gerar feedback e tentar novamente
        4. Repetir até válida ou esgotar tentativas
        """
        text = clause.text
        attempt = 0
        last_formula = ""
        all_errors: list[str] = []

        while attempt < self.max_refinement_attempts:
            attempt += 1

            # Construir prompt
            if attempt == 1:
                prompt = self._build_translation_prompt(text, modality)
            else:
                prompt = self._build_refinement_prompt(text, last_formula, all_errors, modality)

            # Chamar LLM
            formula = self._call_llm(prompt)
            last_formula = formula

            # Validar
            is_valid, errors = self.validator.validate(formula)

            if is_valid:
                return TranslationResult(
                    original_text=text,
                    fol_formula=formula,
                    is_valid=True,
                    validation_errors=[],
                    attempts=attempt,
                    predicates_used=self._extract_predicates(formula),
                    constants_used=self._extract_constants(formula),
                )

            all_errors = errors

        # Esgotou tentativas
        return TranslationResult(
            original_text=text,
            fol_formula=last_formula,
            is_valid=False,
            validation_errors=all_errors,
            attempts=attempt,
            predicates_used=self._extract_predicates(last_formula),
            constants_used=self._extract_constants(last_formula),
        )

    def _build_translation_prompt(
        self, text: str, modality: DeonticModality | None
    ) -> str:
        """Constrói o prompt de tradução inicial."""
        ontology_desc = self.ontology.get_ontology_description()

        modality_hint = ""
        if modality:
            modality_hint = f"\nEsta cláusula foi classificada como: {modality.value}"

        return f"""Você é um especialista em tradução de linguagem jurídica para Lógica de Primeira Ordem (FOL).

{ontology_desc}

## Tarefa
Traduza a seguinte cláusula contratual para uma fórmula em Lógica de Primeira Ordem.
{modality_hint}

## Cláusula
{text}

## Instruções
1. Use APENAS os predicados da ontologia fornecida
2. Use quantificadores quando apropriado (∀ para universal, ∃ para existencial)
3. Use conectivos lógicos: ∧ (e), ∨ (ou), → (implica), ¬ (não), ↔ (se e somente se)
4. Identifique claramente os agentes (CONTRATANTE, CONTRATADO, etc.) como constantes
5. A fórmula deve capturar a semântica normativa da cláusula

## Exemplos
- "O PATROCINADOR obriga-se a pagar mensalmente" →
  Obrigacao(patrocinador, Pagamento(mensal), FimMes)

- "O CONTRATADO não poderá utilizar a marca sem autorização" →
  Proibicao(contratado, UsoMarca(sem_autorizacao))

- "Se houver atraso, haverá multa" →
  Condicao(Atraso, Multa)

## Resposta
Forneça APENAS a fórmula FOL, sem explicações adicionais.
Fórmula FOL:"""

    def _build_refinement_prompt(
        self,
        text: str,
        previous_formula: str,
        errors: list[str],
        modality: DeonticModality | None,
    ) -> str:
        """Constrói prompt de refinamento baseado em erros."""
        errors_str = "\n".join(f"- {e}" for e in errors)

        return f"""A tradução anterior contém erros que precisam ser corrigidos.

## Cláusula Original
{text}

## Tradução Anterior (com erros)
{previous_formula}

## Erros Detectados
{errors_str}

## Predicados Disponíveis na Ontologia
{', '.join(self.ontology.list_predicates())}

## Instruções de Correção
1. Corrija os erros listados acima
2. Use APENAS predicados da ontologia
3. Verifique o balanceamento de parênteses
4. Certifique-se que todas as variáveis estão quantificadas

## Resposta
Forneça APENAS a fórmula FOL corrigida:"""

    def _call_llm(self, prompt: str) -> str:
        """Chama o LLM e extrai a fórmula da resposta."""
        try:
            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                # OpenAI-style
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=500,
                )
                result = response.choices[0].message.content
            elif hasattr(self.llm_client, "messages"):
                # Anthropic-style
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.content[0].text
            elif hasattr(self.llm_client, "generate_content"):
                # Google Gemini
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.2,
                        "max_output_tokens": 500,
                    },
                )
                result = response.text
            else:
                raise ValueError("Cliente LLM não reconhecido")

            # Extrair fórmula da resposta
            return self._extract_formula(result)

        except Exception as e:
            return f"ERRO: {e}"

    def _extract_formula(self, response: str) -> str:
        """Extrai a fórmula FOL da resposta do LLM."""
        # Tentar extrair fórmula após marcadores comuns
        markers = ["Fórmula FOL:", "FOL:", "```", "Resposta:"]
        for marker in markers:
            if marker in response:
                parts = response.split(marker)
                if len(parts) > 1:
                    formula = parts[-1].strip()
                    # Remover possíveis markdown code blocks
                    formula = formula.replace("```", "").strip()
                    # Pegar apenas a primeira linha se houver múltiplas
                    lines = [l.strip() for l in formula.split("\n") if l.strip()]
                    if lines:
                        return lines[0]

        # Se não encontrou marcador, retornar resposta limpa
        response = response.strip()
        # Tentar pegar primeira linha não vazia
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        if lines:
            return lines[0]

        return response

    def _translate_heuristic(
        self, clause: Clause, modality: DeonticModality | None
    ) -> TranslationResult:
        """
        Tradução heurística quando LLM não está disponível.

        Usa padrões simples para gerar fórmulas básicas.
        """
        text = clause.text.lower()
        formula = ""

        # Extrair agentes
        agents = []
        agent_patterns = [
            ("patrocinador", "patrocinador"),
            ("contratante", "contratante"),
            ("contratado", "contratado"),
            ("atleta", "atleta"),
            ("cob", "cob"),
        ]
        for pattern, constant in agent_patterns:
            if pattern in text:
                agents.append(constant)

        agent = agents[0] if agents else "agente"

        # Gerar fórmula baseada na modalidade
        if modality == DeonticModality.OBRIGACAO_ATIVA:
            if "pag" in text:
                formula = f"Obrigacao({agent}, Pagamento(valor), Prazo)"
            else:
                formula = f"Obrigacao({agent}, Acao(obrigacao), Prazo)"

        elif modality == DeonticModality.PROIBICAO:
            if "marca" in text:
                formula = f"Proibicao({agent}, UsoMarca(sem_autorizacao))"
            else:
                formula = f"Proibicao({agent}, Acao(proibida))"

        elif modality == DeonticModality.PERMISSAO:
            formula = f"Permissao({agent}, Acao(permitida))"

        elif modality == DeonticModality.CONDICAO:
            formula = "Condicao(Antecedente, Consequente)"

        else:
            formula = f"Definicao({agent}, Papel)"

        is_valid, errors = self.validator.validate(formula)

        return TranslationResult(
            original_text=clause.text,
            fol_formula=formula,
            is_valid=is_valid,
            validation_errors=errors,
            attempts=1,
            predicates_used=self._extract_predicates(formula),
            constants_used=self._extract_constants(formula),
        )

    def _extract_predicates(self, formula: str) -> list[str]:
        """Extrai predicados usados na fórmula."""
        pattern = r"\b([A-Z][a-zA-Z]*)\s*\("
        return list(set(re.findall(pattern, formula)))

    def _extract_constants(self, formula: str) -> list[str]:
        """Extrai constantes usadas na fórmula."""
        # Constantes são palavras em minúsculas que não são variáveis quantificadas
        pattern = r"\b([a-z][a-z_]*)\b"
        all_lower = set(re.findall(pattern, formula))
        # Remover palavras reservadas
        reserved = {"and", "or", "not", "implies", "forall", "exists"}
        return list(all_lower - reserved)

    def update_clause_with_fol(self, clause: Clause) -> Clause:
        """
        Traduz e atualiza a cláusula com a fórmula FOL.
        """
        result = self.translate(clause)
        clause.fol_formula = result.fol_formula
        clause.fol_parsed = result.is_valid
        clause.fol_translation_attempts = result.attempts
        return clause


def translate_clauses(
    clauses: list[Clause], llm_client: Any = None
) -> list[TranslationResult]:
    """
    Função utilitária para traduzir múltiplas cláusulas.
    """
    translator = NLFOLTranslator(llm_client=llm_client)
    return [translator.translate(clause) for clause in clauses]
