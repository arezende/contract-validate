"""
KB axioms for ContractFOL v3 — Etapa 8.

These axioms are hand-curated and auditable.  Each axiom encodes a
verifiable legal constraint derived exclusively from public statute text
(scraped_snippet_1 / scraped_snippet_2 fields or independently-fetched
statute text).  They are NEVER derived from DiscrepancyInstance.explanation
or any other GT-authored justification.

Axiom typologies (spec §7.7):
  deadline_limit        — InconLeg: arithmetic constraints on time periods
  canonical_definition  — MisTermLeg: definitional equivalences
  mandatory_disclosure  — OmisLeg: completeness requirements
  deontic_force         — AmbLeg: mandatory vs. discretionary (v2 marker)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from z3 import Bool, BoolVal, Int, IntVal


# ---------------------------------------------------------------------------
# KBAxiom dataclass
# ---------------------------------------------------------------------------


@dataclass
class KBAxiom:
    """A single axiom in the ContractFOL Legal Knowledge Base."""

    axiom_id: str
    """Unique identifier, e.g. 'fcra_dispute_deadline_30'."""

    statute: str
    """Canonical statute citation, e.g. '15 U.S.C. § 1681i(a)(1)(A)'."""

    description: str
    """Plain-English description of what the axiom encodes."""

    source: str
    """Provenance: 'scraped_snippet_1', 'scraped_snippet_2', or a URL."""

    typology: str
    """One of: 'deadline_limit' | 'canonical_definition' |
    'mandatory_disclosure' | 'deontic_force'."""

    z3_constraint: object
    """The Z3 expression encoding this axiom."""

    label: str
    """Label used in the compiled solver; must start with 'kb_'."""

    v2_only: bool = False
    """True for deontic_force axioms (AmbLeg, v2 feature flag)."""


# ---------------------------------------------------------------------------
# Axiom catalogue
# ---------------------------------------------------------------------------


def build_axioms() -> list[KBAxiom]:
    """
    Return the full list of pre-defined KB axioms.

    All Z3 variable names are intentionally stable so that
    ``compile_rin`` can inject matching ``Int(...)`` assertions from
    parsed RIN elements.
    """
    axioms: list[KBAxiom] = []

    # ------------------------------------------------------------------
    # FCRA — Fair Credit Reporting Act (15 U.S.C. § 1681i)
    # Source: scraped from https://www.law.cornell.edu/uscode/text/15/1681i
    # "not later than 30 days after the date on which the agency receives
    #  notice of the dispute from the consumer"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="fcra_dispute_deadline_30",
            statute="15 U.S.C. § 1681i(a)(1)(A)",
            description=(
                "Credit bureau must complete dispute investigation within 30 days"
            ),
            source="https://www.law.cornell.edu/uscode/text/15/1681i",
            typology="deadline_limit",
            z3_constraint=(Int("dispute_investigation_days") <= IntVal(30)),
            label="kb_fcra_dispute_deadline_30",
        )
    )

    # FCRA — Consumer notification deadline after investigation
    # "not later than 5 business days after the completion of the
    #  reinvestigation" — 15 U.S.C. § 1681i(a)(6)(A)
    axioms.append(
        KBAxiom(
            axiom_id="fcra_notification_deadline_5",
            statute="15 U.S.C. § 1681i(a)(6)(A)",
            description=(
                "Notification of results within 5 business days after completion"
            ),
            source="https://www.law.cornell.edu/uscode/text/15/1681i",
            typology="deadline_limit",
            z3_constraint=(Int("notification_days") <= IntVal(5)),
            label="kb_fcra_notification_deadline_5",
        )
    )

    # ------------------------------------------------------------------
    # UCC § 2-207 — Battle of the Forms
    # Source: https://www.law.cornell.edu/ucc/2/2-207
    # "A definite and seasonable expression of acceptance or a written
    #  confirmation which is sent within a reasonable time operates as an
    #  acceptance even though it states terms additional to or different
    #  from those offered or agreed upon"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="ucc_2_207_acceptance",
            statute="UCC § 2-207",
            description=(
                "A definite expression of acceptance operates as acceptance "
                "even if it states additional terms"
            ),
            source="https://www.law.cornell.edu/ucc/2/2-207",
            typology="canonical_definition",
            z3_constraint=(
                Bool("acceptance_with_additional_terms") == BoolVal(True)
            ),
            label="kb_ucc_2_207_acceptance",
        )
    )

    # ------------------------------------------------------------------
    # WARN Act — 29 U.S.C. § 2102(a)
    # Source: https://www.law.cornell.edu/uscode/text/29/2102
    # "An employer shall not order a plant closing or mass layoff until
    #  the end of a 60-day period after the employer serves written notice"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="warn_act_notice_60",
            statute="29 U.S.C. § 2102(a)",
            description=(
                "Employer must provide 60 days advance notice before plant closing"
            ),
            source="https://www.law.cornell.edu/uscode/text/29/2102",
            typology="deadline_limit",
            z3_constraint=(Int("notice_days") >= IntVal(60)),
            label="kb_warn_act_notice_60",
        )
    )

    # ------------------------------------------------------------------
    # FMLA — Family and Medical Leave Act (29 U.S.C. § 2612(a)(1))
    # Source: https://www.law.cornell.edu/uscode/text/29/2612
    # "an eligible employee shall be entitled to a total of 12 workweeks
    #  of leave during any 12-month period"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="fmla_leave_12_weeks",
            statute="29 U.S.C. § 2612(a)(1)",
            description="Employee entitled to 12 workweeks of leave per year",
            source="https://www.law.cornell.edu/uscode/text/29/2612",
            typology="mandatory_disclosure",
            z3_constraint=(Int("leave_weeks") >= IntVal(12)),
            label="kb_fmla_leave_12_weeks",
        )
    )

    # ------------------------------------------------------------------
    # GDPR Art. 33 — Personal data breach notification (72-hour limit)
    # Source: https://gdpr-info.eu/art-33-gdpr/
    # "not later than 72 hours after having become aware of it, notify
    #  the personal data breach to the supervisory authority"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="gdpr_art33_breach_notification_72h",
            statute="GDPR Art. 33",
            description=(
                "Controller must notify supervisory authority of data breach "
                "within 72 hours of becoming aware"
            ),
            source="https://gdpr-info.eu/art-33-gdpr/",
            typology="deadline_limit",
            z3_constraint=(Int("breach_notification_hours") <= IntVal(72)),
            label="kb_gdpr_art33_breach_notification_72h",
        )
    )

    # ------------------------------------------------------------------
    # Federal Arbitration Act — 9 U.S.C. § 2
    # Source: https://www.law.cornell.edu/uscode/text/9/2
    # Written arbitration clauses in commerce contracts are "valid,
    # irrevocable, and enforceable"
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="faa_arbitration_clause_enforceable",
            statute="9 U.S.C. § 2",
            description=(
                "Written arbitration clause in a commerce contract is valid "
                "and enforceable under the FAA"
            ),
            source="https://www.law.cornell.edu/uscode/text/9/2",
            typology="canonical_definition",
            z3_constraint=(
                Bool("written_arbitration_clause_enforceable") == BoolVal(True)
            ),
            label="kb_faa_arbitration_clause_enforceable",
        )
    )

    # ------------------------------------------------------------------
    # Deontic-force axiom (v2 only) — UCC § 2-207 discretionary terms
    # "between merchants such terms become part of the contract unless..."
    # This axiom requires v2 AmbLeg typology support.
    # ------------------------------------------------------------------

    axioms.append(
        KBAxiom(
            axiom_id="ucc_2_207_merchant_terms_deontic",
            statute="UCC § 2-207(2)",
            description=(
                "Between merchants, additional terms in acceptance become "
                "part of the contract unless they materially alter it or "
                "the offer expressly limits acceptance — deontic: discretionary"
            ),
            source="https://www.law.cornell.edu/ucc/2/2-207",
            typology="deontic_force",
            z3_constraint=(
                Bool("merchant_additional_terms_discretionary") == BoolVal(True)
            ),
            label="kb_ucc_2_207_merchant_terms_deontic",
            v2_only=True,
        )
    )

    return axioms


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_axioms_for_typology(typology: str) -> list[KBAxiom]:
    """Filter axioms by typology.

    Parameters
    ----------
    typology:
        One of: ``'deadline_limit'``, ``'canonical_definition'``,
        ``'mandatory_disclosure'``, ``'deontic_force'``.

    Returns
    -------
    list[KBAxiom]
        All axioms matching the given typology (including v2_only ones).
    """
    return [a for a in build_axioms() if a.typology == typology]


def get_axiom_by_id(axiom_id: str) -> KBAxiom | None:
    """Look up an axiom by its unique axiom_id.

    Parameters
    ----------
    axiom_id:
        The identifier to look up, e.g. ``'fcra_dispute_deadline_30'``.

    Returns
    -------
    KBAxiom | None
        The matching axiom, or None if not found.
    """
    for a in build_axioms():
        if a.axiom_id == axiom_id:
            return a
    return None
