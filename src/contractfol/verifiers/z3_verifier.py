"""
Verificador Formal usando Z3 SMT Solver.

Implementa a verificação de consistência de fórmulas FOL e detecção de conflitos
contratuais, conforme Seção 5.6 da dissertação.

O processo:
1. Conversão para SMT-LIB
2. Declaração de axiomas de background
3. Asserção das fórmulas
4. Verificação via Z3
5. Se UNSAT, identifica unsat core (fórmulas responsáveis pelo conflito)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from z3 import (
    And,
    Bool,
    BoolSort,
    DeclareSort,
    Exists,
    ForAll,
    Function,
    Implies,
    IntSort,
    Not,
    Or,
    RealSort,
    Solver,
    StringSort,
    sat,
    unknown,
    unsat,
)

from contractfol.models import Clause, Conflict, ConflictType, VerificationStatus
from contractfol.ontology import ContractOntology, get_ontology


class Z3ConversionError(Exception):
    """Erro na conversão de FOL para Z3."""

    pass


@dataclass
class VerificationResult:
    """Resultado da verificação Z3."""

    status: VerificationStatus
    conflicts: list[Conflict] = field(default_factory=list)
    unsat_core_formulas: list[str] = field(default_factory=list)
    unsat_core_clause_ids: list[str] = field(default_factory=list)
    verification_time_ms: float = 0.0
    model: Any = None  # Modelo satisfatível se SAT


class Z3Verifier:
    """
    Verificador formal usando Z3 SMT Solver.

    Detecta inconsistências entre cláusulas contratuais formalizadas em FOL.
    """

    def __init__(self, ontology: ContractOntology | None = None, timeout_ms: int = 30000):
        """
        Inicializa o verificador.

        Args:
            ontology: Ontologia de domínio
            timeout_ms: Timeout em milissegundos para o solver
        """
        self.ontology = ontology or get_ontology()
        self.timeout_ms = timeout_ms

        # Sorts Z3
        self._agent_sort = DeclareSort("Agent")
        self._action_sort = DeclareSort("Action")
        self._time_sort = DeclareSort("Time")
        self._contract_sort = DeclareSort("Contract")
        self._resource_sort = DeclareSort("Resource")

        # Predicados Z3 (funções que retornam Bool)
        self._predicates: dict[str, Any] = {}
        self._constants: dict[str, Any] = {}

        self._init_predicates()
        self._init_axioms()

    def _init_predicates(self):
        """Inicializa os predicados Z3 baseados na ontologia."""
        # Predicados deônticos principais
        self._predicates["Obrigacao"] = Function(
            "Obrigacao", self._agent_sort, self._action_sort, self._time_sort, BoolSort()
        )
        self._predicates["Permissao"] = Function(
            "Permissao", self._agent_sort, self._action_sort, BoolSort()
        )
        self._predicates["Proibicao"] = Function(
            "Proibicao", self._agent_sort, self._action_sort, BoolSort()
        )

        # Predicados estruturais
        self._predicates["Parte"] = Function(
            "Parte", self._agent_sort, self._contract_sort, BoolSort()
        )
        self._predicates["Prazo"] = Function(
            "Prazo", self._contract_sort, self._time_sort, self._time_sort, BoolSort()
        )

        # Predicados condicionais
        self._predicates["Condicao"] = Function(
            "Condicao", self._action_sort, self._action_sort, BoolSort()
        )

        # Predicados de ação (retornam Action)
        self._predicates["Pagamento"] = Function(
            "Pagamento", StringSort(), self._action_sort
        )
        self._predicates["UsoMarca"] = Function(
            "UsoMarca", StringSort(), self._action_sort
        )
        self._predicates["UsoImagem"] = Function(
            "UsoImagem", StringSort(), self._action_sort
        )
        self._predicates["Entrega"] = Function(
            "Entrega", StringSort(), self._action_sort
        )

        # Predicado de exclusividade
        self._predicates["Exclusividade"] = Function(
            "Exclusividade", self._agent_sort, self._resource_sort, BoolSort()
        )

        # Predicados temporais
        self._predicates["Antes"] = Function(
            "Antes", self._time_sort, self._time_sort, BoolSort()
        )

    def _init_axioms(self):
        """Inicializa os axiomas de consistência."""
        self._axioms = []

        # Os axiomas são adicionados ao solver durante a verificação
        # para permitir rastreamento no unsat core

    def _get_axioms(self, solver: Solver) -> list[tuple[str, Any]]:
        """
        Retorna os axiomas como assertions rastreáveis.

        Returns:
            Lista de tuplas (nome_do_axioma, formula_z3)
        """
        from z3 import Const

        a = Const("a", self._agent_sort)
        b = Const("b", self._agent_sort)
        p = Const("p", self._action_sort)
        t = Const("t", self._time_sort)

        axioms = []

        # Axioma 1: Obrigação e Proibição são mutuamente exclusivas
        # ∀a,p,t: Obrigacao(a,p,t) → ¬Proibicao(a,p)
        ax1 = ForAll(
            [a, p, t],
            Implies(
                self._predicates["Obrigacao"](a, p, t),
                Not(self._predicates["Proibicao"](a, p)),
            ),
        )
        axioms.append(("axiom_obrigacao_proibicao", ax1))

        # Axioma 2: Proibição implica não-permissão
        # ∀a,p: Proibicao(a,p) → ¬Permissao(a,p)
        ax2 = ForAll(
            [a, p],
            Implies(
                self._predicates["Proibicao"](a, p),
                Not(self._predicates["Permissao"](a, p)),
            ),
        )
        axioms.append(("axiom_proibicao_permissao", ax2))

        # Axioma 3: Obrigação implica Permissão
        # ∀a,p,t: Obrigacao(a,p,t) → Permissao(a,p)
        ax3 = ForAll(
            [a, p, t],
            Implies(
                self._predicates["Obrigacao"](a, p, t), self._predicates["Permissao"](a, p)
            ),
        )
        axioms.append(("axiom_obrigacao_permissao", ax3))

        return axioms

    def verify_consistency(self, clauses: list[Clause]) -> VerificationResult:
        """
        Verifica a consistência de um conjunto de cláusulas.

        Args:
            clauses: Lista de cláusulas com fórmulas FOL

        Returns:
            VerificationResult com status e possíveis conflitos
        """
        import time

        start_time = time.time()

        # Filtrar cláusulas que têm fórmulas FOL válidas
        valid_clauses = [c for c in clauses if c.fol_formula and c.fol_parsed]

        if not valid_clauses:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                verification_time_ms=0,
            )

        # Criar solver
        solver = Solver()
        solver.set("timeout", self.timeout_ms)

        # Mapear cláusula -> assertion para rastreamento
        clause_assertions: dict[str, Any] = {}
        assertion_to_clause: dict[str, str] = {}

        # Adicionar axiomas rastreáveis
        for axiom_name, axiom_formula in self._get_axioms(solver):
            tracker = Bool(axiom_name)
            solver.assert_and_track(axiom_formula, tracker)

        # Converter e adicionar cada fórmula
        for clause in valid_clauses:
            try:
                z3_formula = self._convert_fol_to_z3(clause.fol_formula)
                if z3_formula is not None:
                    tracker_name = f"clause_{clause.id}"
                    tracker = Bool(tracker_name)
                    solver.assert_and_track(z3_formula, tracker)
                    clause_assertions[clause.id] = tracker
                    assertion_to_clause[tracker_name] = clause.id
            except Z3ConversionError as e:
                # Log erro mas continua com outras cláusulas
                print(f"Erro convertendo cláusula {clause.id}: {e}")
                continue

        # Verificar satisfatibilidade
        result = solver.check()
        elapsed_time = (time.time() - start_time) * 1000

        if result == sat:
            return VerificationResult(
                status=VerificationStatus.SAT,
                verification_time_ms=elapsed_time,
                model=solver.model(),
            )

        elif result == unsat:
            # Extrair unsat core
            core = solver.unsat_core()
            core_names = [str(c) for c in core]

            # Identificar cláusulas no core
            conflict_clause_ids = []
            for name in core_names:
                if name in assertion_to_clause:
                    conflict_clause_ids.append(assertion_to_clause[name])

            # Criar objeto Conflict
            conflicts = []
            if conflict_clause_ids:
                conflict = Conflict(
                    id=f"conflict_{len(conflicts) + 1}",
                    conflict_type=self._infer_conflict_type(valid_clauses, conflict_clause_ids),
                    clause_ids=conflict_clause_ids,
                    formulas=[
                        c.fol_formula for c in valid_clauses if c.id in conflict_clause_ids
                    ],
                    unsat_core=core_names,
                    severity="HIGH",
                    confidence=1.0,
                )
                conflicts.append(conflict)

            return VerificationResult(
                status=VerificationStatus.UNSAT,
                conflicts=conflicts,
                unsat_core_formulas=core_names,
                unsat_core_clause_ids=conflict_clause_ids,
                verification_time_ms=elapsed_time,
            )

        else:  # unknown
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                verification_time_ms=elapsed_time,
            )

    def _convert_fol_to_z3(self, formula: str) -> Any:
        """
        Converte uma fórmula FOL em string para expressão Z3.

        Esta é uma conversão simplificada que suporta os padrões mais comuns.
        """
        from z3 import Const, String

        formula = formula.strip()

        # Normalizar operadores
        formula = formula.replace("∧", " And ")
        formula = formula.replace("∨", " Or ")
        formula = formula.replace("→", " -> ")
        formula = formula.replace("↔", " <-> ")
        formula = formula.replace("¬", " Not ")
        formula = formula.replace("∀", "Forall ")
        formula = formula.replace("∃", "Exists ")

        # Parser recursivo simplificado
        try:
            return self._parse_formula(formula)
        except Exception as e:
            raise Z3ConversionError(f"Erro ao converter fórmula: {e}")

    def _parse_formula(self, formula: str) -> Any:
        """Parser recursivo para fórmulas FOL."""
        from z3 import Const, StringVal

        formula = formula.strip()

        # Remover parênteses externos se presentes
        while formula.startswith("(") and formula.endswith(")"):
            # Verificar se são parênteses correspondentes
            if self._matching_parens(formula):
                formula = formula[1:-1].strip()
            else:
                break

        # Quantificador universal
        forall_match = re.match(
            r"Forall\s+([a-z][a-z0-9_]*)\s*\.\s*(.+)", formula, re.IGNORECASE
        )
        if forall_match:
            var_name = forall_match.group(1)
            body = forall_match.group(2)
            var = Const(var_name, self._agent_sort)  # Simplificação: assume Agent
            return ForAll([var], self._parse_formula(body))

        # Quantificador existencial
        exists_match = re.match(
            r"Exists\s+([a-z][a-z0-9_]*)\s*\.\s*(.+)", formula, re.IGNORECASE
        )
        if exists_match:
            var_name = exists_match.group(1)
            body = exists_match.group(2)
            var = Const(var_name, self._agent_sort)
            return Exists([var], self._parse_formula(body))

        # Implicação
        impl_match = self._split_binary(formula, "->")
        if impl_match:
            left, right = impl_match
            return Implies(self._parse_formula(left), self._parse_formula(right))

        # And
        and_match = self._split_binary(formula, "And")
        if and_match:
            left, right = and_match
            return And(self._parse_formula(left), self._parse_formula(right))

        # Or
        or_match = self._split_binary(formula, "Or")
        if or_match:
            left, right = or_match
            return Or(self._parse_formula(left), self._parse_formula(right))

        # Not
        not_match = re.match(r"Not\s+(.+)", formula, re.IGNORECASE)
        if not_match:
            return Not(self._parse_formula(not_match.group(1)))

        # Predicado
        pred_match = re.match(r"([A-Z][a-zA-Z]*)\s*\(([^)]*)\)", formula)
        if pred_match:
            pred_name = pred_match.group(1)
            args_str = pred_match.group(2)
            return self._parse_predicate(pred_name, args_str)

        # Constante booleana
        if formula.lower() == "true":
            return True
        if formula.lower() == "false":
            return False

        # Se não reconheceu, retornar como booleano nomeado
        return Bool(formula)

    def _parse_predicate(self, name: str, args_str: str) -> Any:
        """Parse um predicado com argumentos."""
        from z3 import Const, StringVal

        # Dividir argumentos
        args = self._split_args(args_str)

        if name not in self._predicates:
            # Predicado desconhecido: criar booleano
            return Bool(f"{name}_{hash(args_str) % 10000}")

        pred = self._predicates[name]

        # Converter argumentos para constantes Z3 apropriadas
        z3_args = []
        for arg in args:
            arg = arg.strip()
            if not arg:
                continue

            # Verificar se é um predicado aninhado
            nested_match = re.match(r"([A-Z][a-zA-Z]*)\s*\(([^)]*)\)", arg)
            if nested_match:
                z3_args.append(self._parse_predicate(nested_match.group(1), nested_match.group(2)))
            elif arg.startswith('"') or arg.startswith("'"):
                # String literal
                z3_args.append(StringVal(arg.strip("\"'")))
            else:
                # Constante ou variável
                # Inferir tipo pelo contexto (simplificação)
                if name in ["Obrigacao", "Permissao", "Proibicao", "Parte", "Exclusividade"]:
                    if len(z3_args) == 0:
                        z3_args.append(Const(arg, self._agent_sort))
                    elif len(z3_args) == 1:
                        z3_args.append(Const(arg, self._action_sort))
                    else:
                        z3_args.append(Const(arg, self._time_sort))
                elif name in ["Pagamento", "UsoMarca", "UsoImagem", "Entrega"]:
                    z3_args.append(StringVal(arg))
                elif name == "Prazo":
                    if len(z3_args) == 0:
                        z3_args.append(Const(arg, self._contract_sort))
                    else:
                        z3_args.append(Const(arg, self._time_sort))
                else:
                    z3_args.append(Const(arg, self._action_sort))

        if z3_args:
            return pred(*z3_args)
        return Bool(name)

    def _split_args(self, args_str: str) -> list[str]:
        """Divide argumentos respeitando parênteses aninhados."""
        args = []
        current = ""
        depth = 0

        for char in args_str:
            if char == "," and depth == 0:
                args.append(current.strip())
                current = ""
            else:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                current += char

        if current.strip():
            args.append(current.strip())

        return args

    def _split_binary(self, formula: str, operator: str) -> tuple[str, str] | None:
        """Divide fórmula em operador binário respeitando parênteses."""
        depth = 0
        # Procurar operador fora de parênteses
        op_len = len(operator)

        for i in range(len(formula) - op_len + 1):
            char = formula[i]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif depth == 0:
                if formula[i : i + op_len].lower() == operator.lower():
                    # Verificar que não é parte de palavra
                    before_ok = i == 0 or not formula[i - 1].isalnum()
                    after_ok = (
                        i + op_len >= len(formula) or not formula[i + op_len].isalnum()
                    )
                    if before_ok and after_ok:
                        left = formula[:i].strip()
                        right = formula[i + op_len :].strip()
                        if left and right:
                            return (left, right)

        return None

    def _matching_parens(self, formula: str) -> bool:
        """Verifica se parênteses externos são correspondentes."""
        if not (formula.startswith("(") and formula.endswith(")")):
            return False

        depth = 0
        for i, char in enumerate(formula):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and i < len(formula) - 1:
                return False

        return depth == 0

    def _infer_conflict_type(
        self, clauses: list[Clause], conflict_ids: list[str]
    ) -> ConflictType:
        """Infere o tipo de conflito baseado nas cláusulas envolvidas."""
        conflict_clauses = [c for c in clauses if c.id in conflict_ids]

        has_obrigacao = any(
            c.modality in [DeonticModality.OBRIGACAO_ATIVA, DeonticModality.OBRIGACAO_PASSIVA]
            for c in conflict_clauses
            if c.modality
        )
        has_proibicao = any(
            c.modality == DeonticModality.PROIBICAO for c in conflict_clauses if c.modality
        )

        if has_obrigacao and has_proibicao:
            return ConflictType.OBRIGACAO_PROIBICAO

        return ConflictType.OBRIGACOES_MUTUAMENTE_EXCLUSIVAS


# Importar DeonticModality que foi esquecido
from contractfol.models import DeonticModality


def verify_clauses(clauses: list[Clause]) -> VerificationResult:
    """
    Função utilitária para verificar consistência de cláusulas.
    """
    verifier = Z3Verifier()
    return verifier.verify_consistency(clauses)
