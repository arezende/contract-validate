"""
KB store for ContractFOL v3 — Etapa 8.

Loads KB axioms, queries by relevance to a DiscrepancyInstance, and
returns (z3_expr, label) tuples ready for injection into compile_rin.
"""

from __future__ import annotations

import re

from contractfol.corpus.schema import DiscrepancyInstance
from contractfol.kb.axioms import KBAxiom, build_axioms


# ---------------------------------------------------------------------------
# Normalisation helpers (shared with mine_citations)
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Lowercase, strip whitespace, collapse spaces around §."""
    s = text.strip().lower()
    s = re.sub(r"\s*§\s*", "§", s)
    s = re.sub(r" {2,}", " ", s)
    return s


# ---------------------------------------------------------------------------
# KBStore
# ---------------------------------------------------------------------------


class KBStore:
    """
    The ContractFOL Legal Knowledge Base store.

    Loads and filters KBAxiom objects and provides query methods for
    integration with the Z3 compiler pipeline.

    Parameters
    ----------
    include_v2:
        If False (default), axioms marked ``v2_only=True`` are excluded.
        Set to True to include deontic-force axioms (AmbLeg, v2).
    """

    def __init__(self, include_v2: bool = False) -> None:
        self._axioms: list[KBAxiom] = [
            a for a in build_axioms()
            if include_v2 or not a.v2_only
        ]

    # ------------------------------------------------------------------
    # Core query methods
    # ------------------------------------------------------------------

    def get_all_constraints(self) -> list[tuple]:
        """Return (z3_constraint, label) for all loaded axioms.

        Returns
        -------
        list[tuple]
            Parallel list of (z3 expression, label string) pairs.
        """
        return [(a.z3_constraint, a.label) for a in self._axioms]

    def get_constraints_for_instance(
        self,
        instance: DiscrepancyInstance,
    ) -> list[tuple]:
        """Return relevant (z3_constraint, label) tuples for an instance.

        Relevance heuristic
        -------------------
        1. If ``instance.law_citation`` matches an axiom's statute via
           normalised substring match, return those axiom constraints.
        2. If no match, return all ``deadline_limit`` axioms as a
           conservative fallback (they rarely cause false positives).
        3. Never return v2_only axioms unless ``include_v2=True``.

        Parameters
        ----------
        instance:
            A DiscrepancyInstance (any dimension; legal instances are
            most likely to yield specific matches).

        Returns
        -------
        list[tuple]
            List of (z3 expression, label string) pairs.
        """
        citation = instance.law_citation
        if citation:
            norm_cite = _normalise(citation)
            matched = [
                (a.z3_constraint, a.label)
                for a in self._axioms
                if norm_cite in _normalise(a.statute)
                or _normalise(a.statute) in norm_cite
            ]
            if matched:
                return matched

        # Fallback: return all deadline_limit axioms
        return [
            (a.z3_constraint, a.label)
            for a in self._axioms
            if a.typology == "deadline_limit"
        ]

    # ------------------------------------------------------------------
    # Provenance / auditing
    # ------------------------------------------------------------------

    def get_provenance_table(self) -> list[dict]:
        """Return a provenance table for dissertation auditing.

        Returns
        -------
        list[dict]
            Each dict contains:
            ``axiom_id``, ``statute``, ``typology``, ``source``,
            ``description``, ``v2_only``.
        """
        return [
            {
                "axiom_id": a.axiom_id,
                "statute": a.statute,
                "typology": a.typology,
                "source": a.source,
                "description": a.description,
                "v2_only": a.v2_only,
            }
            for a in self._axioms
        ]

    def to_yaml(self, path: str) -> None:
        """Serialise provenance table to YAML for auditing.

        Parameters
        ----------
        path:
            Destination file path (will be overwritten if it exists).
        """
        try:
            import yaml  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "PyYAML is required for KBStore.to_yaml. "
                "Install it with: pip install pyyaml"
            ) from exc

        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(
                self.get_provenance_table(),
                fh,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
