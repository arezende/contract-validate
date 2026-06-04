"""
Deterministic RIN → Z3 compiler.

ZERO LLM calls — this is pure Python + z3-solver.

Strategy
--------
Each NormElement becomes a Z3 Bool constant asserting the norm holds.
Direct contradictions (obligation + prohibition on same action, or two
deadlines for the same event with different numeric values) are detected
and encoded as additional constraints so that the resulting solver state
becomes UNSAT.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from z3 import (
    And,
    Bool,
    BoolVal,
    Implies,
    Int,
    Not,
    Or,
    Solver,
    sat,
    unsat,
)

from contractfol.rin.schema import NormElement, RIN

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class CompiledRIN:
    """Result of compiling a RIN to Z3 constraints."""

    constraints: list = field(default_factory=list)
    """z3 expressions — one per source constraint."""

    labels: list[str] = field(default_factory=list)
    """labels[i] is the element_id (or axiom id) that produced constraints[i]."""

    solver: Solver = field(default_factory=Solver)
    """Pre-loaded solver (not yet checked)."""

    assumption_vars: list = field(default_factory=list)
    """z3 Bool vars for unsat-core extraction (parallel to constraints)."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _second_arg(predicate_form: str) -> Optional[str]:
    """
    Extract the second argument from a predicate string such as
    ``Obrigacao(Contractor, deliver_goods, always)`` → ``deliver_goods``.

    Returns None if the form cannot be parsed.
    """
    m = re.search(r"\(\s*[^,)]+\s*,\s*([^,)]+)", predicate_form)
    if m:
        return m.group(1).strip()
    return None


def _first_arg(predicate_form: str) -> Optional[str]:
    """
    Extract the first argument from a predicate string such as
    ``Prazo(delivery_event, 30)`` → ``delivery_event``.
    """
    m = re.search(r"\(\s*([^,)]+)", predicate_form)
    if m:
        return m.group(1).strip()
    return None


def _extract_numbers(text: str) -> list[int]:
    """Return all non-negative integers found in *text*."""
    return [int(t) for t in re.findall(r"\b\d+\b", text)]


def _predicate_name(predicate_form: str) -> Optional[str]:
    """
    Return the top-level predicate name, e.g. ``Obrigacao`` from
    ``Obrigacao(Contractor, deliver, always)``.
    """
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", predicate_form)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------


def _detect_direct_contradiction(elements: list[NormElement]) -> list:
    """
    Find pairs of NormElements that directly contradict each other:

    1. Same action (second argument), one ``Obrigacao`` + one ``Proibicao``.
    2. Same event (first argument) for two ``Prazo`` elements that carry
       different numeric values (deadline conflict).

    Returns a list of z3 Bool constraints to add (empty if none found).
    """
    extra: list = []

    # --- Rule 1: obligation ↔ prohibition on same action ------------------
    obligations: dict[str, list[NormElement]] = {}  # action → elements
    prohibitions: dict[str, list[NormElement]] = {}

    for elem in elements:
        pname = _predicate_name(elem.predicate_form)
        action = _second_arg(elem.predicate_form)
        if action is None:
            continue
        if pname == "Obrigacao" or elem.kind == "obligation":
            obligations.setdefault(action, []).append(elem)
        elif pname == "Proibicao" or elem.kind == "prohibition":
            prohibitions.setdefault(action, []).append(elem)

    for action, obl_list in obligations.items():
        if action in prohibitions:
            for obl in obl_list:
                for proh in prohibitions[action]:
                    # Assert that it is impossible for both norms to hold
                    # simultaneously: Not(And(obl, proh)).
                    b_obl = Bool(obl.element_id)
                    b_proh = Bool(proh.element_id)
                    extra.append(Not(And(b_obl, b_proh)))
                    logger.debug(
                        "Contradiction detected: obligation %s ↔ prohibition %s (action=%s)",
                        obl.element_id,
                        proh.element_id,
                        action,
                    )

    # --- Rule 2: two Prazo elements for same event with different values --
    deadline_groups: dict[str, list[NormElement]] = {}
    for elem in elements:
        if elem.kind != "deadline":
            continue
        event = _first_arg(elem.predicate_form)
        if event is None:
            continue
        deadline_groups.setdefault(event, []).append(elem)

    for event, dl_list in deadline_groups.items():
        if len(dl_list) < 2:
            continue
        for i in range(len(dl_list)):
            nums_i = _extract_numbers(dl_list[i].predicate_form)
            for j in range(i + 1, len(dl_list)):
                nums_j = _extract_numbers(dl_list[j].predicate_form)
                if nums_i and nums_j and nums_i[0] != nums_j[0]:
                    # Create Int constants for the two deadlines and assert
                    # they must be equal (because they refer to the same
                    # event) — but also assert their actual values, forcing
                    # UNSAT.
                    d_i = Int(f"deadline_{dl_list[i].element_id}")
                    d_j = Int(f"deadline_{dl_list[j].element_id}")
                    extra.append(d_i == nums_i[0])
                    extra.append(d_j == nums_j[0])
                    extra.append(d_i == d_j)  # same event → must agree
                    logger.debug(
                        "Deadline conflict: %s(%d) ↔ %s(%d) for event=%s",
                        dl_list[i].element_id,
                        nums_i[0],
                        dl_list[j].element_id,
                        nums_j[0],
                        event,
                    )

    return extra


# ---------------------------------------------------------------------------
# Main compiler
# ---------------------------------------------------------------------------


def compile_rin(
    rin: RIN,
    kb_axioms: list | None = None,
) -> CompiledRIN:
    """
    Compile a RIN to Z3 constraints.

    kb_axioms: optional list of (z3_expr, label_str) tuples from the KB.

    Each NormElement becomes a Z3 Bool constant named after element_id.
    The base constraint is: Bool(element_id) == True (the norm is asserted
    to hold).

    Contradiction constraints (obligation ↔ prohibition on same action, or
    conflicting deadlines) are added on top of the base constraints.
    """
    result = CompiledRIN()

    # --- Base constraint: every norm is asserted to hold ------------------
    for elem in rin.elements:
        b = Bool(elem.element_id)
        constraint = b == BoolVal(True)
        result.constraints.append(constraint)
        result.labels.append(elem.element_id)

    # --- Direct-contradiction constraints ---------------------------------
    contradiction_exprs = _detect_direct_contradiction(rin.elements)
    for i, expr in enumerate(contradiction_exprs):
        result.constraints.append(expr)
        result.labels.append(f"contradiction_{i}")

    # --- Optional KB axioms -----------------------------------------------
    if kb_axioms:
        for kb_expr, kb_label in kb_axioms:
            result.constraints.append(kb_expr)
            result.labels.append(kb_label)

    # --- Load solver ------------------------------------------------------
    solver = Solver()
    for constraint in result.constraints:
        solver.add(constraint)
    result.solver = solver

    return result


# ---------------------------------------------------------------------------
# Unsat-core support
# ---------------------------------------------------------------------------


def build_assumption_solver(compiled: CompiledRIN) -> tuple[Solver, list]:
    """
    Returns (solver, assumption_vars) ready for unsat-core extraction.

    Each constraints[i] is added as: Implies(assumption_vars[i], constraints[i]).
    Call ``solver.check(*assumption_vars)`` to get the core via
    ``solver.unsat_core()``.
    """
    solver = Solver()
    assumption_vars = []

    for i, constraint in enumerate(compiled.constraints):
        label = compiled.labels[i] if i < len(compiled.labels) else f"a{i}"
        # Use the label as the Bool name so unsat_core() returns readable labels.
        a = Bool(label)
        assumption_vars.append(a)
        solver.add(Implies(a, constraint))

    return solver, assumption_vars
