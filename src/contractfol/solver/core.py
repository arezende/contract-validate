"""
Unsat core extraction → span + explanation.

Given a VerifyResult with sat_result=="unsat", extract the conflicting
NormElements and build a human-readable explanation without calling an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contractfol.rin.schema import RIN, NormElement


@dataclass
class UnsatCore:
    instance_id: str
    conflicting_elements: list[NormElement]   # the NormElements in the core
    conflicting_labels: list[str]             # includes KB axiom labels if legal
    span: str                                 # concatenated source_clause texts
    explanation: str                          # auto-generated explanation
    dimension: str | None                     # "in_text" | "legal"


def _first_arg_from_predicate(predicate_form: str) -> str | None:
    """Extract the first argument after the predicate name, e.g. 'Contractor' from Obrigacao(Contractor, ...)."""
    m = re.search(r'\(([^,)]+)', predicate_form)
    if m:
        return m.group(1).strip()
    return None


def _second_arg_from_predicate(predicate_form: str) -> str | None:
    """Extract the second argument, e.g. 'deliver_goods' from Obrigacao(Contractor, deliver_goods, ...)."""
    m = re.search(r'\(\s*[^,)]+\s*,\s*([^,)]+)', predicate_form)
    if m:
        return m.group(1).strip()
    return None


def _build_explanation(conflicting_elements: list[NormElement]) -> str:
    """
    Auto-generate a plain-English explanation of the contradiction without an LLM.

    Templates:
    - obligation + prohibition → "Conflict: '{action}' is simultaneously obligated and prohibited."
    - Two deadline elements   → "Conflict: deadline for '{event}' is set to contradictory values."
    - Generic                 → "Conflict: the following normative elements are mutually inconsistent: {element_ids}."
    """
    if not conflicting_elements:
        return "Conflict: mutually inconsistent normative elements detected."

    kinds = [e.kind for e in conflicting_elements]
    element_ids = [e.element_id for e in conflicting_elements]

    # obligation + prohibition conflict
    has_obligation = any(k == "obligation" for k in kinds)
    has_prohibition = any(k == "prohibition" for k in kinds)
    if has_obligation and has_prohibition:
        # Try to extract the action (second arg) from an obligation or prohibition element
        action = None
        for e in conflicting_elements:
            if e.kind in ("obligation", "prohibition"):
                action = _second_arg_from_predicate(e.predicate_form)
                if action:
                    break
        if action:
            return f"Conflict: '{action}' is simultaneously obligated and prohibited."
        return "Conflict: an action is simultaneously obligated and prohibited."

    # Two deadline elements
    deadline_elements = [e for e in conflicting_elements if e.kind == "deadline"]
    if len(deadline_elements) >= 2:
        event = _first_arg_from_predicate(deadline_elements[0].predicate_form)
        if event:
            return f"Conflict: deadline for '{event}' is set to contradictory values."
        return "Conflict: deadline is set to contradictory values."

    # Generic fallback
    ids_str = ", ".join(element_ids)
    return f"Conflict: the following normative elements are mutually inconsistent: {ids_str}."


def extract_core(
    rin: RIN,
    verify_result: "VerifyResult",  # noqa: F821 — forward ref at runtime
) -> "UnsatCore | None":
    """
    Given a VerifyResult with sat_result=="unsat", extract the UnsatCore.
    Returns None if verify_result is not UNSAT.

    span: join the source_clause of each conflicting NormElement with " | "
    explanation: generated from the conflicting elements — describe the contradiction
                 in plain English without calling an LLM.
    """
    if verify_result.sat_result != "unsat":
        return None

    # Build a lookup map from element_id → NormElement
    elem_map = {e.element_id: e for e in rin.elements}

    # Collect conflicting elements using the core_element_ids from verify_result
    conflicting_elements: list[NormElement] = []
    for eid in verify_result.core_element_ids:
        if eid in elem_map:
            conflicting_elements.append(elem_map[eid])

    # If core_element_ids didn't yield any known elements, fall back to core_labels
    if not conflicting_elements:
        for lbl in verify_result.core_labels:
            if lbl in elem_map:
                conflicting_elements.append(elem_map[lbl])

    # If still empty, include ALL elements (best-effort fallback)
    if not conflicting_elements:
        conflicting_elements = list(rin.elements)

    span = " | ".join(e.source_clause for e in conflicting_elements)
    explanation = _build_explanation(conflicting_elements)

    return UnsatCore(
        instance_id=rin.instance_id,
        conflicting_elements=conflicting_elements,
        conflicting_labels=verify_result.core_labels,
        span=span,
        explanation=explanation,
        dimension=verify_result.dimension,
    )


def core_to_span_dict(core: UnsatCore) -> dict:
    """
    Returns a dict compatible with Eval_3 output:
    {"location": span, "explanation": explanation, "law_citation": None}
    The law_citation is filled by the KB layer (not here).
    """
    return {
        "location": core.span,
        "explanation": core.explanation,
        "law_citation": None,
    }
