"""
CT3 Refinement Loop — Etapa 7 of ContractFOL v3.

Two-UNSAT protocol enforcement
--------------------------------
- Syntactic refinement: triggered by Z3 parse/type errors. Safe to apply
  to BOTH original and changed variants.
- Semantic refinement: triggered by UNSAT result. Applied ONLY to the
  ``original`` variant (spurious UNSAT = translator error, not a defect).
  NEVER applied to ``changed`` — UNSAT on changed_text IS the defect signal.

Violating this rule is a critical methodology error (spec §8).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from z3 import sat, unsat

from contractfol.llm.interface import generate
from contractfol.nl2fol.compile_z3 import build_assumption_solver, compile_rin
from contractfol.rin.schema import NormElement, RIN, Symbol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RefinementAttempt:
    attempt_number: int
    trigger: str               # "syntactic" | "semantic"
    error_message: str         # what triggered this refinement
    rin_before: RIN
    rin_after: RIN | None      # None if LLM failed to produce valid RIN
    sat_result: str | None     # result after re-running solver on rin_after


@dataclass
class RefinementResult:
    instance_id: str
    variant: str               # "original" | "changed"
    final_rin: RIN
    converged: bool            # True if reached SAT (for original) or stable parse (for changed)
    attempts: list[RefinementAttempt] = field(default_factory=list)
    total_attempts: int = 0
    final_sat_result: str | None = None
    refinement_applied: bool = False   # True if any refinement actually ran


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYNTACTIC_PROMPT = """\
You are formalizing a legal clause in First-Order Logic.
The previous formalization attempt produced the following error:

Error: {error_message}

Original clause:
{clause_text}

Previous formalization (with errors):
{rin_json}

Fix the formalization so it is syntactically valid.
Ensure all predicate forms follow this convention:
- Obrigacao(agente, acao, condicao)
- Proibicao(agente, acao, condicao)
- Permissao(agente, acao, condicao)
- Prazo(evento, tempo)
- Definicao(termo, escopo)
- Penalidade(agente, violacao, sancao)

Return ONLY a JSON array of normative elements:
[{{"element_id": str, "source_clause": str, "location": null, "kind": str, "deontic_force": null, "predicate_form": str}}, ...]"""

_SEMANTIC_PROMPT = """\
You are formalizing a legal clause in First-Order Logic.
The formalization produced an UNSAT result, which means the formal representation
contains a contradiction that does not exist in the original text.

Original clause (which is consistent — there is no real contradiction):
{clause_text}

The following elements are in conflict:
{conflicting_elements_json}

Please rewrite these elements so they are mutually consistent while still
faithfully representing the original clause text.

Return ONLY a JSON array of the corrected normative elements (same format as before):
[{{"element_id": str, "source_clause": str, "location": null, "kind": str, "deontic_force": null, "predicate_form": str}}, ...]"""


# ---------------------------------------------------------------------------
# LLM response parser
# ---------------------------------------------------------------------------


def _parse_elements_from_response(response: str) -> list[NormElement] | None:
    """
    Parse a JSON array of normative element dicts from an LLM response string.

    Returns a list of NormElement objects, or None if parsing fails.
    """
    # Strip markdown code fences if present
    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])

    # Try to find a JSON array in the response
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        logger.warning("No JSON array found in LLM response: %r", response[:200])
        return None

    json_str = text[start : end + 1]
    try:
        raw_list = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("JSON decode error parsing LLM response: %s", exc)
        return None

    if not isinstance(raw_list, list) or len(raw_list) == 0:
        logger.warning("LLM returned empty or non-list JSON: %r", raw_list)
        return None

    elements: list[NormElement] = []
    for item in raw_list:
        if not isinstance(item, dict):
            logger.warning("Non-dict item in LLM element list: %r", item)
            return None
        try:
            elem = NormElement(**item)
            elements.append(elem)
        except Exception as exc:
            logger.warning("Failed to construct NormElement from %r: %s", item, exc)
            return None

    return elements if elements else None


# ---------------------------------------------------------------------------
# Refinement steps
# ---------------------------------------------------------------------------


async def _syntactic_refine_step(
    clause_text: str,
    rin: RIN,
    error_message: str,
    model_alias: str,
) -> RIN | None:
    """
    Ask the LLM to fix a syntactic/parse error in the RIN.
    Returns a new RIN or None if the LLM response is unparseable.
    """
    rin_json = json.dumps(
        [e.model_dump() for e in rin.elements],
        ensure_ascii=False,
        indent=2,
    )
    prompt = _SYNTACTIC_PROMPT.format(
        error_message=error_message,
        clause_text=clause_text,
        rin_json=rin_json,
    )

    try:
        response = await generate(prompt, model_alias)
    except Exception as exc:
        logger.error("LLM call failed during syntactic refinement: %s", exc)
        return None

    elements = _parse_elements_from_response(response)
    if elements is None:
        logger.warning(
            "Syntactic refinement produced unparseable response for instance %s",
            rin.instance_id,
        )
        return None

    try:
        new_rin = RIN(
            instance_id=rin.instance_id,
            variant=rin.variant,
            symbols=rin.symbols,
            elements=elements,
            translator_model=rin.translator_model,
        )
    except Exception as exc:
        logger.warning("Failed to build new RIN after syntactic refinement: %s", exc)
        return None

    return new_rin


async def _semantic_refine_step(
    clause_text: str,
    rin: RIN,
    unsat_core_labels: list[str],
    model_alias: str,
) -> RIN | None:
    """
    Ask the LLM to resolve a spurious UNSAT by rewriting the conflicting elements.
    Only called for variant == "original".
    """
    # Build the conflicting elements JSON from labels
    elem_map = {e.element_id: e for e in rin.elements}
    conflicting: list[NormElement] = []
    for label in unsat_core_labels:
        if label in elem_map:
            conflicting.append(elem_map[label])

    # Fallback: if labels don't map to elements, use all elements
    if not conflicting:
        conflicting = list(rin.elements)

    conflicting_elements_json = json.dumps(
        [e.model_dump() for e in conflicting],
        ensure_ascii=False,
        indent=2,
    )
    prompt = _SEMANTIC_PROMPT.format(
        clause_text=clause_text,
        conflicting_elements_json=conflicting_elements_json,
    )

    try:
        response = await generate(prompt, model_alias)
    except Exception as exc:
        logger.error("LLM call failed during semantic refinement: %s", exc)
        return None

    elements = _parse_elements_from_response(response)
    if elements is None:
        logger.warning(
            "Semantic refinement produced unparseable response for instance %s",
            rin.instance_id,
        )
        return None

    # Merge: replace only the conflicting element_ids with the new versions,
    # keep non-conflicting elements unchanged.
    conflicting_ids = {e.element_id for e in conflicting}
    new_elements_map = {e.element_id: e for e in elements}
    merged: list[NormElement] = []
    for elem in rin.elements:
        if elem.element_id in conflicting_ids and elem.element_id in new_elements_map:
            merged.append(new_elements_map[elem.element_id])
        else:
            merged.append(elem)
    # Also add any brand-new elements that the LLM returned
    existing_ids = {e.element_id for e in rin.elements}
    for e in elements:
        if e.element_id not in existing_ids:
            merged.append(e)

    if not merged:
        logger.warning("Merged element list is empty after semantic refinement.")
        return None

    try:
        new_rin = RIN(
            instance_id=rin.instance_id,
            variant=rin.variant,
            symbols=rin.symbols,
            elements=merged,
            translator_model=rin.translator_model,
        )
    except Exception as exc:
        logger.warning("Failed to build new RIN after semantic refinement: %s", exc)
        return None

    return new_rin


# ---------------------------------------------------------------------------
# Main refinement loop
# ---------------------------------------------------------------------------


async def refine(
    clause_text: str,
    initial_rin: RIN,
    model_alias: str,
    max_attempts: int = 3,
    kb_axioms: list | None = None,
) -> RefinementResult:
    """
    CT3 refinement loop.

    For variant == "original":
        Run full CT3: syntactic (on parse error) + semantic (on UNSAT).
        Goal: reach SAT. Converged = True when SAT achieved or max_attempts exceeded.

    For variant == "changed":
        Run syntactic refinement ONLY (on parse/type errors from Z3).
        NEVER run semantic refinement — UNSAT on changed_text is the detection signal.
        Converged = True when solver can evaluate the formula (regardless of SAT/UNSAT).

    Returns RefinementResult with the final RIN after all refinement attempts.
    """
    result = RefinementResult(
        instance_id=initial_rin.instance_id,
        variant=initial_rin.variant,
        final_rin=initial_rin,
        converged=False,
    )
    current_rin = initial_rin

    # Track the last sat_str so we can populate final_sat_result even when
    # the loop exits without a refinement attempt (immediate convergence).
    sat_str: str | None = None
    error_msg: str | None = None
    compiled = None

    for attempt_num in range(1, max_attempts + 1):
        # 1. Try to compile and check
        try:
            compiled = compile_rin(current_rin, kb_axioms)
            solver, assumptions = build_assumption_solver(compiled)
            sat_result_z3 = solver.check(*assumptions)
            if sat_result_z3 == sat:
                sat_str = "sat"
            elif sat_result_z3 == unsat:
                sat_str = "unsat"
            else:
                sat_str = "unknown"
            error_msg = None
        except Exception as exc:
            sat_str = "error"
            error_msg = str(exc)
            compiled = None

        # 2. Check convergence
        if current_rin.variant == "original":
            if sat_str == "sat":
                result.converged = True
                break
            elif sat_str == "error":
                trigger = "syntactic"
            else:  # unsat or unknown
                trigger = "semantic"
        else:  # changed — NEVER apply semantic refinement
            if sat_str in ("sat", "unsat", "unknown"):
                result.converged = True   # solver ran successfully — accept result
                break
            else:  # error
                trigger = "syntactic"

        # 3. Apply appropriate refinement
        new_rin: RIN | None = None
        if trigger == "syntactic":
            new_rin = await _syntactic_refine_step(
                clause_text, current_rin, error_msg or sat_str, model_alias
            )
        else:  # semantic — only reached for original variant
            core_labels: list[str] = []
            if compiled is not None:
                try:
                    core_labels = [str(a) for a in solver.unsat_core()]
                except Exception:
                    core_labels = []
            new_rin = await _semantic_refine_step(
                clause_text, current_rin, core_labels, model_alias
            )

        attempt = RefinementAttempt(
            attempt_number=attempt_num,
            trigger=trigger,
            error_message=error_msg or sat_str or "",
            rin_before=current_rin,
            rin_after=new_rin,
            sat_result=sat_str,
        )
        result.attempts.append(attempt)
        result.refinement_applied = True

        if new_rin is None:
            break  # LLM failed — stop refining
        current_rin = new_rin

    result.final_rin = current_rin
    result.total_attempts = len(result.attempts)
    result.final_sat_result = sat_str
    return result


# ---------------------------------------------------------------------------
# Sync convenience wrapper
# ---------------------------------------------------------------------------


def refine_sync(
    clause_text: str,
    initial_rin: RIN,
    model_alias: str,
    max_attempts: int = 3,
    kb_axioms: list | None = None,
) -> RefinementResult:
    """Synchronous wrapper around :func:`refine`."""
    import asyncio

    return asyncio.run(
        refine(clause_text, initial_rin, model_alias, max_attempts, kb_axioms)
    )
