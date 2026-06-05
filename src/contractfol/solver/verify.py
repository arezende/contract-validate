"""
SAT/UNSAT verdict + two-UNSAT protocol + in-text/legal classification.

Two-UNSAT protocol
------------------
| UNSAT origin    | Meaning                   | Action                                    |
|-----------------|---------------------------|-------------------------------------------|
| On original_text | Translator error          | Log as spurious UNSAT; count toward H₂   |
| On changed_text  | Real defect detected      | Report as Eval_1 = True (defect present)  |
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from z3 import sat, unsat, unknown

from contractfol.rin.schema import RIN
from contractfol.nl2fol.compile_z3 import compile_rin, build_assumption_solver

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    instance_id: str
    variant: str               # "original" | "changed"
    sat_result: str            # "sat" | "unsat" | "unknown" | "timeout"
    is_defect: bool            # True only if variant=="changed" AND sat_result=="unsat"
    is_spurious_unsat: bool    # True if variant=="original" AND sat_result=="unsat"
    dimension: str | None      # "in_text" | "legal" | None
    core_element_ids: list[str]  # element_ids in the unsat core
    core_labels: list[str]       # full labels (may include KB axiom ids)
    solver_time_ms: float
    error: str | None = None


def verify(
    rin: RIN,
    kb_axioms: list | None = None,    # list of (z3_expr, label_str) from KB
    timeout_ms: int = 30_000,
) -> VerifyResult:
    """
    Run SAT check on a compiled RIN.

    kb_axioms: optional KB constraints for legal dimension classification.

    Returns a VerifyResult with full two-UNSAT protocol applied:
    - If UNSAT on original variant: logged as spurious (translator error)
    - If UNSAT on changed variant: flagged as real defect
    """
    try:
        compiled = compile_rin(rin, kb_axioms)
        solver, assumptions = build_assumption_solver(compiled)
        solver.set("timeout", timeout_ms)

        t_start = time.monotonic()
        try:
            result = solver.check(*assumptions)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t_start) * 1000.0
            logger.error("Solver raised exception for %s: %s", rin.instance_id, exc)
            return VerifyResult(
                instance_id=rin.instance_id,
                variant=rin.variant,
                sat_result="error",
                is_defect=False,
                is_spurious_unsat=False,
                dimension=None,
                core_element_ids=[],
                core_labels=[],
                solver_time_ms=elapsed_ms,
                error=str(exc),
            )
        elapsed_ms = (time.monotonic() - t_start) * 1000.0

        if result == sat:
            return VerifyResult(
                instance_id=rin.instance_id,
                variant=rin.variant,
                sat_result="sat",
                is_defect=False,
                is_spurious_unsat=False,
                dimension=None,
                core_element_ids=[],
                core_labels=[],
                solver_time_ms=elapsed_ms,
            )

        elif result == unsat:
            # Extract unsat core
            core = solver.unsat_core()
            core_labels: list[str] = []
            core_element_ids: list[str] = []

            for a in core:
                a_str = str(a)
                # Labels are the assumption variable names (which equal element_ids or axiom ids)
                core_labels.append(a_str)
                # element_ids are those that don't start with "kb_" or "axiom_" or "contradiction_"
                if not (a_str.startswith("kb_") or a_str.startswith("axiom_") or a_str.startswith("contradiction_")):
                    core_element_ids.append(a_str)

            # Dimension classification
            dimension: str | None = None
            if core_labels:
                if any(lbl.startswith("kb_") or lbl.startswith("axiom_") for lbl in core_labels):
                    dimension = "legal"
                else:
                    dimension = "in_text"

            is_defect = (rin.variant == "changed") and True
            is_spurious_unsat = (rin.variant == "original")

            if is_spurious_unsat:
                logger.warning(
                    "Spurious UNSAT detected for instance %s (variant=original). "
                    "This indicates a translator error (H₂ metric). Core labels: %s",
                    rin.instance_id,
                    core_labels,
                )
            elif is_defect:
                logger.info(
                    "Defect detected for instance %s (Eval_1=True). "
                    "Dimension: %s. Core labels: %s",
                    rin.instance_id,
                    dimension,
                    core_labels,
                )

            return VerifyResult(
                instance_id=rin.instance_id,
                variant=rin.variant,
                sat_result="unsat",
                is_defect=is_defect,
                is_spurious_unsat=is_spurious_unsat,
                dimension=dimension,
                core_element_ids=core_element_ids,
                core_labels=core_labels,
                solver_time_ms=elapsed_ms,
            )

        else:
            # unknown (timeout or solver gave up)
            logger.warning(
                "Solver returned unknown/timeout for instance %s after %.1f ms",
                rin.instance_id,
                elapsed_ms,
            )
            return VerifyResult(
                instance_id=rin.instance_id,
                variant=rin.variant,
                sat_result="unknown",
                is_defect=False,
                is_spurious_unsat=False,
                dimension=None,
                core_element_ids=[],
                core_labels=[],
                solver_time_ms=elapsed_ms,
            )

    except Exception as exc:
        logger.exception("Unexpected error during verify for %s", rin.instance_id)
        return VerifyResult(
            instance_id=rin.instance_id,
            variant=rin.variant,
            sat_result="error",
            is_defect=False,
            is_spurious_unsat=False,
            dimension=None,
            core_element_ids=[],
            core_labels=[],
            solver_time_ms=0.0,
            error=str(exc),
        )
