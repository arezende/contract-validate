"""
Base de Conhecimento ContractFOL.

Armazena afirmações (fatos) e regras para testar dinamicamente os predicados.
Permite validação semântica e inferência básica sobre contratos.

Estrutura:
- Assertions: Fatos concretos sobre um contrato específico
- Rules: Regras de inferência genéricas
- Queries: Consultas predefinidas para validação

Exemplo de uso:
    kb = KnowledgeBase()
    kb.add_assertion("Parte(cob, contrato_001)")
    kb.add_assertion("Obrigacao(patrocinador, Pagamento(mensal), FimMes)")

    conflicts = kb.check_consistency()
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from enum import Enum


class AssertionType(Enum):
    """Tipos de asserções na base de conhecimento."""

    FACT = "FACT"          # Fato concreto extraído do contrato
    INFERRED = "INFERRED"  # Fato inferido por regras
    HYPOTHESIS = "HYPOTHESIS"  # Hipótese para teste
    NEGATION = "NEGATION"  # Negação explícita


class AssertionStatus(Enum):
    """Status de uma asserção."""

    ACTIVE = "ACTIVE"      # Asserção ativa
    RETRACTED = "RETRACTED"  # Asserção retratada
    CONFLICTING = "CONFLICTING"  # Asserção em conflito


@dataclass
class Assertion:
    """Uma asserção (fato) na base de conhecimento."""

    id: str
    formula: str  # Fórmula FOL
    assertion_type: AssertionType = AssertionType.FACT
    status: AssertionStatus = AssertionStatus.ACTIVE

    # Proveniência
    source_clause_id: str = ""
    source_text: str = ""
    contract_id: str = ""

    # Metadados
    confidence: float = 1.0
    created_at: str = ""
    created_by: str = ""  # "user", "llm", "inference"

    # Relacionamentos
    inferred_from: list[str] = field(default_factory=list)  # IDs de asserções base
    related_assertions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "formula": self.formula,
            "assertion_type": self.assertion_type.value,
            "status": self.status.value,
            "source_clause_id": self.source_clause_id,
            "source_text": self.source_text,
            "contract_id": self.contract_id,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "inferred_from": self.inferred_from,
            "related_assertions": self.related_assertions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Assertion":
        return cls(
            id=data["id"],
            formula=data["formula"],
            assertion_type=AssertionType(data.get("assertion_type", "FACT")),
            status=AssertionStatus(data.get("status", "ACTIVE")),
            source_clause_id=data.get("source_clause_id", ""),
            source_text=data.get("source_text", ""),
            contract_id=data.get("contract_id", ""),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", ""),
            inferred_from=data.get("inferred_from", []),
            related_assertions=data.get("related_assertions", []),
        )


@dataclass
class InferenceRule:
    """Regra de inferência na base de conhecimento."""

    id: str
    name: str
    description: str

    # Padrão da regra
    antecedent_pattern: str  # Padrão FOL que deve estar presente
    consequent_template: str  # Template do consequente a gerar

    # Condições
    requires_predicates: list[str] = field(default_factory=list)

    # Metadados
    confidence: float = 1.0
    priority: int = 0  # Regras com maior prioridade são aplicadas primeiro
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InferenceRule":
        return cls(**data)


@dataclass
class ConsistencyResult:
    """Resultado de uma verificação de consistência."""

    is_consistent: bool
    conflicts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_assertions: int = 0
    check_time_ms: float = 0.0


class KnowledgeBase:
    """
    Base de conhecimento para armazenamento e raciocínio sobre contratos.

    Funcionalidades:
    - Armazenamento de fatos (asserções)
    - Regras de inferência
    - Verificação de consistência
    - Consultas sobre a base
    - Persistência em JSON
    """

    def __init__(self, persistence_path: str | None = None):
        """
        Inicializa a base de conhecimento.

        Args:
            persistence_path: Caminho para arquivo JSON de persistência
        """
        self.assertions: dict[str, Assertion] = {}
        self.rules: dict[str, InferenceRule] = {}
        self.persistence_path = persistence_path

        self._assertion_counter = 0
        self._indices: dict[str, set[str]] = {
            "by_contract": {},
            "by_predicate": {},
            "by_clause": {},
        }

        # Carregar regras padrão
        self._load_default_rules()

        # Carregar dados persistidos
        if persistence_path:
            self._load_from_file()

    def _load_default_rules(self):
        """Carrega regras de inferência padrão."""

        # Regra 1: Obrigação implica Permissão
        self.add_rule(InferenceRule(
            id="rule_obrig_perm",
            name="Obrigação implica Permissão",
            description="Se um agente é obrigado a fazer algo, então é permitido fazê-lo",
            antecedent_pattern=r"Obrigacao\((\w+),\s*([^,]+),\s*([^)]+)\)",
            consequent_template="Permissao({agent}, {action})",
            requires_predicates=["Obrigacao"],
            confidence=1.0,
            priority=10,
        ))

        # Regra 2: Proibição implica não-Permissão
        self.add_rule(InferenceRule(
            id="rule_proib_nperm",
            name="Proibição implica não-Permissão",
            description="Se um agente é proibido de fazer algo, então não é permitido",
            antecedent_pattern=r"Proibicao\((\w+),\s*([^)]+)\)",
            consequent_template="¬Permissao({agent}, {action})",
            requires_predicates=["Proibicao"],
            confidence=1.0,
            priority=10,
        ))

        # Regra 3: Exclusividade impede uso por outros
        self.add_rule(InferenceRule(
            id="rule_exclusiv",
            name="Exclusividade é exclusiva",
            description="Exclusividade de um recurso impede uso por outros agentes",
            antecedent_pattern=r"Exclusividade\((\w+),\s*([^)]+)\)",
            consequent_template="∀x.(x ≠ {agent} → ¬Permissao(x, Uso({resource})))",
            requires_predicates=["Exclusividade"],
            confidence=0.95,
            priority=5,
        ))

        # Regra 4: Condição ativa consequência
        self.add_rule(InferenceRule(
            id="rule_condicao",
            name="Condição dispara consequência",
            description="Se uma condição é verdadeira, sua consequência também é",
            antecedent_pattern=r"Condicao\(([^,]+),\s*([^)]+)\)",
            consequent_template="({condition} → {consequence})",
            requires_predicates=["Condicao"],
            confidence=1.0,
            priority=8,
        ))

    def _generate_assertion_id(self) -> str:
        """Gera um ID único para asserção."""
        self._assertion_counter += 1
        return f"A{self._assertion_counter:05d}"

    def add_assertion(
        self,
        formula: str,
        assertion_type: AssertionType = AssertionType.FACT,
        source_clause_id: str = "",
        source_text: str = "",
        contract_id: str = "",
        confidence: float = 1.0,
        created_by: str = "user",
    ) -> Assertion:
        """
        Adiciona uma asserção à base de conhecimento.

        Args:
            formula: Fórmula FOL da asserção
            assertion_type: Tipo da asserção
            source_clause_id: ID da cláusula fonte
            source_text: Texto original da cláusula
            contract_id: ID do contrato
            confidence: Confiança na asserção (0.0 a 1.0)
            created_by: Origem da asserção

        Returns:
            A asserção criada
        """
        assertion = Assertion(
            id=self._generate_assertion_id(),
            formula=formula,
            assertion_type=assertion_type,
            status=AssertionStatus.ACTIVE,
            source_clause_id=source_clause_id,
            source_text=source_text,
            contract_id=contract_id,
            confidence=confidence,
            created_at=datetime.now().isoformat(),
            created_by=created_by,
        )

        self.assertions[assertion.id] = assertion

        # Atualizar índices
        self._index_assertion(assertion)

        # Persistir
        if self.persistence_path:
            self._save_to_file()

        return assertion

    def add_assertions_from_clauses(
        self,
        clauses: list[dict],
        contract_id: str = "",
    ) -> list[Assertion]:
        """
        Adiciona múltiplas asserções a partir de cláusulas traduzidas.

        Args:
            clauses: Lista de dicts com 'id', 'text', 'fol_formula'
            contract_id: ID do contrato

        Returns:
            Lista de asserções criadas
        """
        assertions = []
        for clause in clauses:
            if clause.get("fol_formula"):
                assertion = self.add_assertion(
                    formula=clause["fol_formula"],
                    source_clause_id=clause.get("id", ""),
                    source_text=clause.get("text", ""),
                    contract_id=contract_id,
                    created_by="translation",
                )
                assertions.append(assertion)
        return assertions

    def _index_assertion(self, assertion: Assertion):
        """Indexa uma asserção para busca rápida."""
        # Por contrato
        if assertion.contract_id:
            if assertion.contract_id not in self._indices["by_contract"]:
                self._indices["by_contract"][assertion.contract_id] = set()
            self._indices["by_contract"][assertion.contract_id].add(assertion.id)

        # Por predicado
        predicates = self._extract_predicates(assertion.formula)
        for pred in predicates:
            if pred not in self._indices["by_predicate"]:
                self._indices["by_predicate"][pred] = set()
            self._indices["by_predicate"][pred].add(assertion.id)

        # Por cláusula
        if assertion.source_clause_id:
            if assertion.source_clause_id not in self._indices["by_clause"]:
                self._indices["by_clause"][assertion.source_clause_id] = set()
            self._indices["by_clause"][assertion.source_clause_id].add(assertion.id)

    def _extract_predicates(self, formula: str) -> list[str]:
        """Extrai nomes de predicados de uma fórmula."""
        pattern = r"\b([A-Z][a-zA-Z]*)\s*\("
        return list(set(re.findall(pattern, formula)))

    def get_assertion(self, assertion_id: str) -> Assertion | None:
        """Retorna uma asserção pelo ID."""
        return self.assertions.get(assertion_id)

    def get_assertions_by_contract(self, contract_id: str) -> list[Assertion]:
        """Retorna todas as asserções de um contrato."""
        ids = self._indices["by_contract"].get(contract_id, set())
        return [self.assertions[aid] for aid in ids if aid in self.assertions]

    def get_assertions_by_predicate(self, predicate: str) -> list[Assertion]:
        """Retorna todas as asserções que usam um predicado."""
        ids = self._indices["by_predicate"].get(predicate, set())
        return [self.assertions[aid] for aid in ids if aid in self.assertions]

    def retract_assertion(self, assertion_id: str) -> bool:
        """
        Retrata (desativa) uma asserção.

        Returns:
            True se retratada, False se não encontrada
        """
        if assertion_id not in self.assertions:
            return False

        self.assertions[assertion_id].status = AssertionStatus.RETRACTED

        if self.persistence_path:
            self._save_to_file()

        return True

    def add_rule(self, rule: InferenceRule) -> None:
        """Adiciona uma regra de inferência."""
        self.rules[rule.id] = rule

    def apply_inference_rules(self) -> list[Assertion]:
        """
        Aplica regras de inferência para gerar novas asserções.

        Returns:
            Lista de novas asserções inferidas
        """
        new_assertions = []

        # Ordenar regras por prioridade
        sorted_rules = sorted(
            self.rules.values(),
            key=lambda r: r.priority,
            reverse=True
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Encontrar asserções que correspondem ao antecedente
            for assertion in self.assertions.values():
                if assertion.status != AssertionStatus.ACTIVE:
                    continue

                match = re.search(rule.antecedent_pattern, assertion.formula)
                if match:
                    # Gerar consequente
                    groups = match.groups()
                    consequent = self._instantiate_template(
                        rule.consequent_template,
                        groups,
                        rule
                    )

                    if consequent and not self._assertion_exists(consequent):
                        new_assertion = self.add_assertion(
                            formula=consequent,
                            assertion_type=AssertionType.INFERRED,
                            contract_id=assertion.contract_id,
                            confidence=rule.confidence * assertion.confidence,
                            created_by="inference",
                        )
                        new_assertion.inferred_from = [assertion.id]
                        new_assertions.append(new_assertion)

        return new_assertions

    def _instantiate_template(
        self,
        template: str,
        groups: tuple,
        rule: InferenceRule
    ) -> str | None:
        """Instancia um template de consequente."""
        try:
            # Mapeamento básico de grupos para variáveis
            var_names = ["agent", "action", "time", "resource", "condition", "consequence"]
            replacements = {}
            for i, value in enumerate(groups):
                if i < len(var_names):
                    replacements[var_names[i]] = value

            result = template
            for var, value in replacements.items():
                result = result.replace(f"{{{var}}}", value)

            return result
        except Exception:
            return None

    def _assertion_exists(self, formula: str) -> bool:
        """Verifica se uma asserção com a fórmula já existe."""
        normalized = formula.replace(" ", "")
        for assertion in self.assertions.values():
            if assertion.formula.replace(" ", "") == normalized:
                return True
        return False

    def check_consistency(self) -> ConsistencyResult:
        """
        Verifica a consistência da base de conhecimento.

        Detecta conflitos como:
        - Obrigação e Proibição para mesmo agente/ação
        - Permissão e Proibição para mesmo agente/ação
        - Valores inconsistentes

        Returns:
            Resultado da verificação com conflitos encontrados
        """
        import time
        start_time = time.time()

        conflicts = []
        warnings = []

        active_assertions = [
            a for a in self.assertions.values()
            if a.status == AssertionStatus.ACTIVE
        ]

        # Verificar conflitos Obrigação-Proibição
        obrigacoes = self.get_assertions_by_predicate("Obrigacao")
        proibicoes = self.get_assertions_by_predicate("Proibicao")

        for obrig in obrigacoes:
            if obrig.status != AssertionStatus.ACTIVE:
                continue
            obrig_match = re.search(r"Obrigacao\((\w+),\s*([^,]+)", obrig.formula)
            if not obrig_match:
                continue

            obrig_agent, obrig_action = obrig_match.groups()

            for proib in proibicoes:
                if proib.status != AssertionStatus.ACTIVE:
                    continue
                proib_match = re.search(r"Proibicao\((\w+),\s*([^)]+)", proib.formula)
                if not proib_match:
                    continue

                proib_agent, proib_action = proib_match.groups()

                # Verificar se são o mesmo agente e ação similar
                if obrig_agent == proib_agent and self._actions_match(obrig_action, proib_action):
                    conflicts.append({
                        "type": "OBRIGACAO_PROIBICAO",
                        "assertion_ids": [obrig.id, proib.id],
                        "formulas": [obrig.formula, proib.formula],
                        "description": f"Agente '{obrig_agent}' é obrigado e proibido de realizar '{obrig_action}'",
                        "severity": "HIGH",
                    })
                    obrig.status = AssertionStatus.CONFLICTING
                    proib.status = AssertionStatus.CONFLICTING

        # Verificar conflitos Permissão-Proibição
        permissoes = self.get_assertions_by_predicate("Permissao")

        for perm in permissoes:
            if perm.status != AssertionStatus.ACTIVE:
                continue
            perm_match = re.search(r"Permissao\((\w+),\s*([^)]+)", perm.formula)
            if not perm_match:
                continue

            perm_agent, perm_action = perm_match.groups()

            for proib in proibicoes:
                if proib.status != AssertionStatus.ACTIVE:
                    continue
                proib_match = re.search(r"Proibicao\((\w+),\s*([^)]+)", proib.formula)
                if not proib_match:
                    continue

                proib_agent, proib_action = proib_match.groups()

                if perm_agent == proib_agent and self._actions_match(perm_action, proib_action):
                    conflicts.append({
                        "type": "PERMISSAO_PROIBICAO",
                        "assertion_ids": [perm.id, proib.id],
                        "formulas": [perm.formula, proib.formula],
                        "description": f"Agente '{perm_agent}' é permitido e proibido de realizar '{perm_action}'",
                        "severity": "HIGH",
                    })

        # Verificar valores inconsistentes
        valores = self.get_assertions_by_predicate("Valor")
        valor_map: dict[str, list] = {}

        for valor in valores:
            if valor.status != AssertionStatus.ACTIVE:
                continue
            match = re.search(r"Valor\(([^,]+),\s*([^,]+)", valor.formula)
            if match:
                acao, val = match.groups()
                key = acao.strip()
                if key not in valor_map:
                    valor_map[key] = []
                valor_map[key].append((valor, val.strip()))

        for acao, vals in valor_map.items():
            if len(vals) > 1:
                unique_vals = set(v[1] for v in vals)
                if len(unique_vals) > 1:
                    conflicts.append({
                        "type": "VALOR_INCONSISTENTE",
                        "assertion_ids": [v[0].id for v in vals],
                        "formulas": [v[0].formula for v in vals],
                        "description": f"Valores inconsistentes para '{acao}': {unique_vals}",
                        "severity": "MEDIUM",
                    })

        elapsed = (time.time() - start_time) * 1000

        return ConsistencyResult(
            is_consistent=len(conflicts) == 0,
            conflicts=conflicts,
            warnings=warnings,
            checked_assertions=len(active_assertions),
            check_time_ms=elapsed,
        )

    def _actions_match(self, action1: str, action2: str) -> bool:
        """Verifica se duas ações são equivalentes ou similares."""
        # Normalizar
        a1 = action1.lower().strip().rstrip(")")
        a2 = action2.lower().strip().rstrip(")")

        # Igualdade direta
        if a1 == a2:
            return True

        # Uma contém a outra
        if a1 in a2 or a2 in a1:
            return True

        return False

    def query(
        self,
        predicate: str | None = None,
        agent: str | None = None,
        contract_id: str | None = None,
        assertion_type: AssertionType | None = None,
        min_confidence: float = 0.0,
    ) -> list[Assertion]:
        """
        Consulta a base de conhecimento.

        Args:
            predicate: Filtrar por predicado
            agent: Filtrar por agente
            contract_id: Filtrar por contrato
            assertion_type: Filtrar por tipo
            min_confidence: Confiança mínima

        Returns:
            Lista de asserções que correspondem aos filtros
        """
        results = []

        # Começar com todas ou filtradas por predicado
        if predicate:
            candidates = self.get_assertions_by_predicate(predicate)
        elif contract_id:
            candidates = self.get_assertions_by_contract(contract_id)
        else:
            candidates = list(self.assertions.values())

        for assertion in candidates:
            # Filtrar por status
            if assertion.status == AssertionStatus.RETRACTED:
                continue

            # Filtrar por contrato
            if contract_id and assertion.contract_id != contract_id:
                continue

            # Filtrar por tipo
            if assertion_type and assertion.assertion_type != assertion_type:
                continue

            # Filtrar por confiança
            if assertion.confidence < min_confidence:
                continue

            # Filtrar por agente
            if agent:
                if agent.lower() not in assertion.formula.lower():
                    continue

            results.append(assertion)

        return results

    def generate_test_cases(self, predicate: str) -> list[dict]:
        """
        Gera casos de teste para um predicado.

        Args:
            predicate: Nome do predicado

        Returns:
            Lista de casos de teste com exemplos positivos e negativos
        """
        test_cases = []

        assertions = self.get_assertions_by_predicate(predicate)

        for assertion in assertions:
            if assertion.status != AssertionStatus.ACTIVE:
                continue

            # Caso positivo
            test_cases.append({
                "type": "positive",
                "formula": assertion.formula,
                "expected": True,
                "description": f"Asserção existente: {assertion.formula}",
                "source_assertion_id": assertion.id,
            })

            # Gerar caso negativo (negação)
            negated = f"¬({assertion.formula})"
            test_cases.append({
                "type": "negative",
                "formula": negated,
                "expected": False,
                "description": f"Negação deve ser inconsistente: {negated}",
                "source_assertion_id": assertion.id,
            })

        return test_cases

    def export_to_smtlib(self, contract_id: str | None = None) -> str:
        """
        Exporta asserções no formato SMT-LIB.

        Args:
            contract_id: Filtrar por contrato (opcional)

        Returns:
            Código SMT-LIB
        """
        lines = [
            "; ContractFOL Knowledge Base Export",
            f"; Generated at: {datetime.now().isoformat()}",
            "",
        ]

        assertions = (
            self.get_assertions_by_contract(contract_id)
            if contract_id
            else list(self.assertions.values())
        )

        for assertion in assertions:
            if assertion.status != AssertionStatus.ACTIVE:
                continue

            # Converter FOL para SMT-LIB básico
            smtlib = self._fol_to_smtlib(assertion.formula)
            lines.append(f"; {assertion.id}: {assertion.source_text[:50]}..." if assertion.source_text else f"; {assertion.id}")
            lines.append(f"(assert {smtlib})")

        return "\n".join(lines)

    def _fol_to_smtlib(self, formula: str) -> str:
        """Converte fórmula FOL para SMT-LIB (simplificado)."""
        result = formula

        # Substituir operadores
        result = result.replace("∧", " and ")
        result = result.replace("∨", " or ")
        result = result.replace("→", " => ")
        result = result.replace("¬", "(not ")
        result = result.replace("∀", "(forall ")
        result = result.replace("∃", "(exists ")

        return result

    def get_statistics(self) -> dict[str, Any]:
        """Retorna estatísticas da base de conhecimento."""
        active = [a for a in self.assertions.values() if a.status == AssertionStatus.ACTIVE]

        predicate_counts = {}
        for assertion in active:
            for pred in self._extract_predicates(assertion.formula):
                predicate_counts[pred] = predicate_counts.get(pred, 0) + 1

        return {
            "total_assertions": len(self.assertions),
            "active_assertions": len(active),
            "retracted_assertions": sum(1 for a in self.assertions.values() if a.status == AssertionStatus.RETRACTED),
            "conflicting_assertions": sum(1 for a in self.assertions.values() if a.status == AssertionStatus.CONFLICTING),
            "inferred_assertions": sum(1 for a in active if a.assertion_type == AssertionType.INFERRED),
            "total_rules": len(self.rules),
            "active_rules": sum(1 for r in self.rules.values() if r.enabled),
            "contracts": len(self._indices["by_contract"]),
            "predicate_usage": predicate_counts,
            "avg_confidence": sum(a.confidence for a in active) / len(active) if active else 0.0,
        }

    def _save_to_file(self):
        """Salva a base de conhecimento em arquivo JSON."""
        if not self.persistence_path:
            return

        path = Path(self.persistence_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "assertions": [a.to_dict() for a in self.assertions.values()],
            "rules": [r.to_dict() for r in self.rules.values()],
            "counter": self._assertion_counter,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_file(self):
        """Carrega a base de conhecimento de arquivo JSON."""
        if not self.persistence_path:
            return

        path = Path(self.persistence_path)
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._assertion_counter = data.get("counter", 0)

            for a_data in data.get("assertions", []):
                assertion = Assertion.from_dict(a_data)
                self.assertions[assertion.id] = assertion
                self._index_assertion(assertion)

            for r_data in data.get("rules", []):
                rule = InferenceRule.from_dict(r_data)
                self.rules[rule.id] = rule

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Aviso: Erro ao carregar base de conhecimento: {e}")

    def clear(self, keep_rules: bool = True):
        """
        Limpa a base de conhecimento.

        Args:
            keep_rules: Se True, mantém as regras de inferência
        """
        self.assertions.clear()
        self._indices = {
            "by_contract": {},
            "by_predicate": {},
            "by_clause": {},
        }
        self._assertion_counter = 0

        if not keep_rules:
            self.rules.clear()
            self._load_default_rules()

        if self.persistence_path:
            self._save_to_file()


# Instância global
_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base(persistence_path: str | None = None) -> KnowledgeBase:
    """Retorna a instância global da base de conhecimento."""
    global _knowledge_base

    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(persistence_path)

    return _knowledge_base


def reset_knowledge_base():
    """Reseta a instância global."""
    global _knowledge_base
    _knowledge_base = None
