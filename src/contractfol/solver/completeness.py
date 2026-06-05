"""
Omission completeness check — separate mechanism from SAT/UNSAT.

Omission defects are absences, not contradictions. They cannot be detected
by SAT/UNSAT. This module provides a separate structural completeness check
against required normative elements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contractfol.rin.schema import RIN
from contractfol.corpus.schema import DiscrepancyInstance


@dataclass
class CompletenessResult:
    instance_id: str
    is_omission_detected: bool
    missing_elements: list[str]   # kinds or predicate names that are absent
    explanation: str


def check_completeness(
    rin: RIN,
    required_kinds: list[str] | None = None,
    required_predicates: list[str] | None = None,
) -> CompletenessResult:
    """
    Check if the RIN is missing required normative elements.

    required_kinds: list of NormElement.kind values that MUST be present
                    (e.g., ["obligation"] for a contract that must have obligations)
    required_predicates: list of predicate name prefixes that must appear
                         in at least one predicate_form
                         (e.g., ["Penalidade"] for penalty disclosure)

    is_omission_detected = True if any required element is absent.
    """
    missing: list[str] = []

    # Check for required kinds
    if required_kinds:
        present_kinds = {e.kind for e in rin.elements}
        for kind in required_kinds:
            if kind not in present_kinds:
                missing.append(kind)

    # Check for required predicates
    if required_predicates:
        present_predicates: set[str] = set()
        for elem in rin.elements:
            pf = elem.predicate_form.strip()
            # Extract the predicate name (everything before the first '(')
            paren_idx = pf.find("(")
            if paren_idx > 0:
                present_predicates.add(pf[:paren_idx].strip())
            else:
                present_predicates.add(pf)

        for pred_prefix in required_predicates:
            # Check if any present predicate starts with the required prefix
            if not any(p.startswith(pred_prefix) for p in present_predicates):
                missing.append(pred_prefix)

    is_omission_detected = len(missing) > 0

    if is_omission_detected:
        missing_str = ", ".join(f"'{m}'" for m in missing)
        explanation = (
            f"Omission detected: the following required normative elements are absent: {missing_str}."
        )
    else:
        explanation = "No omissions detected; all required normative elements are present."

    return CompletenessResult(
        instance_id=rin.instance_id,
        is_omission_detected=is_omission_detected,
        missing_elements=missing,
        explanation=explanation,
    )


def check_completeness_from_instance(
    rin: RIN,
    instance: DiscrepancyInstance,
) -> CompletenessResult:
    """
    Derive required_kinds/predicates from the instance's perturb_type.

    For omission perturb_type: require that all kinds present in the
    original_rin are also present in the changed_rin.

    This is a placeholder — full KB-driven completeness check is Etapa 8 (kb/).
    """
    # For omission perturbations, we require at least "obligation" as a default
    # heuristic (contracts must have obligations).  A full implementation would
    # parse the original_text via the RIN pipeline and compare kinds.
    required_kinds: list[str] | None = None
    required_predicates: list[str] | None = None

    if instance.perturb_type == "omission":
        # Placeholder: require "obligation" as the baseline completeness check.
        # Full KB-driven logic will be implemented in Etapa 8.
        required_kinds = ["obligation"]

    return check_completeness(
        rin,
        required_kinds=required_kinds,
        required_predicates=required_predicates,
    )
