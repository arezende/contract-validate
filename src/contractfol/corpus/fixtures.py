"""Synthetic fixture instances for ContractFOL unit tests and smoke tests.

These instances are entirely fictional and are used only for testing — they
do NOT represent real CLAUSE dataset entries.
"""

from __future__ import annotations

from typing import get_args

from contractfol.corpus.schema import DiscrepancyInstance, Dimension, PerturbType

# All valid (perturb_type, dimension) combinations — 5 × 2 = 10 cells.
_PERTURB_TYPES: tuple[str, ...] = get_args(PerturbType)
_DIMENSIONS: tuple[str, ...] = get_args(Dimension)

# Pre-defined fixture data for each of the 10 cells.  Each entry is a dict
# of DiscrepancyInstance fields (excluding instance_id, which is assigned
# dynamically) with realistic-looking but entirely fictional contract text.
_CELL_TEMPLATES: list[dict] = [
    # ── ambiguity × in_text ─────────────────────────────────────────────────
    {
        "source_dataset": "cuad",
        "perturb_type": "ambiguity",
        "dimension": "in_text",
        "original_text": (
            "Contractor shall deliver the Software within thirty (30) calendar days "
            "following receipt of a written purchase order signed by both parties."
        ),
        "changed_text": (
            "Contractor shall deliver the Software within a reasonable time following "
            "receipt of the purchase order."
        ),
        "explanation": (
            "'A reasonable time' is ambiguous: it replaces a concrete 30-day deadline "
            "with an undefined period, making enforcement unpredictable."
        ),
        "location": "Section 4.1 — Delivery",
    },
    # ── ambiguity × legal ───────────────────────────────────────────────────
    {
        "source_dataset": "nli",
        "perturb_type": "ambiguity",
        "dimension": "legal",
        "original_text": (
            "The parties agree that any dispute arising under this Agreement shall be "
            "submitted to binding arbitration administered by the American Arbitration "
            "Association under its Commercial Arbitration Rules."
        ),
        "changed_text": (
            "The parties agree that any dispute may be resolved through appropriate "
            "legal channels as determined by the prevailing party."
        ),
        "explanation": (
            "'Appropriate legal channels' is legally ambiguous and conflicts with "
            "mandatory arbitration requirements under the FAA (9 U.S.C. § 1 et seq.)."
        ),
        "location": "Section 12 — Dispute Resolution",
        "contradicted_law": "Federal Arbitration Act",
        "law_citation": "9 U.S.C. § 2",
        "law_url1": "https://www.law.cornell.edu/uscode/text/9/2",
        "scraped_snippet_1": (
            "A written provision in... a contract evidencing a transaction involving "
            "commerce to settle by arbitration a controversy thereafter arising out of "
            "such contract... shall be valid, irrevocable, and enforceable."
        ),
    },
    # ── inconsistency × in_text ─────────────────────────────────────────────
    {
        "source_dataset": "cuad",
        "perturb_type": "inconsistency",
        "dimension": "in_text",
        "original_text": (
            "Payment terms are Net 30 from invoice date. Late payments shall incur an "
            "interest charge of 1.5% per month on the outstanding balance."
        ),
        "changed_text": (
            "Payment terms are Net 30 from invoice date. Late payments shall incur an "
            "interest charge of 1.5% per month on the outstanding balance. "
            "All invoices must be paid within 15 days of receipt."
        ),
        "explanation": (
            "The contract now specifies two contradictory payment deadlines: "
            "Net 30 in the first sentence and 15 days in the added sentence."
        ),
        "location": "Section 6.2 — Payment Terms",
        "contradicted_location": "Section 6.2 — Payment Terms",
        "contradicted_text": "Payment terms are Net 30 from invoice date.",
    },
    # ── inconsistency × legal ───────────────────────────────────────────────
    {
        "source_dataset": "nli",
        "perturb_type": "inconsistency",
        "dimension": "legal",
        "original_text": (
            "The Employer shall provide at least two (2) weeks written notice prior to "
            "terminating this Agreement without cause."
        ),
        "changed_text": (
            "The Employer may terminate this Agreement without cause and without any "
            "prior notice to the Employee."
        ),
        "explanation": (
            "The at-will termination clause without notice contradicts WARN Act "
            "obligations (29 U.S.C. § 2102) for covered employers requiring 60 days "
            "advance notice for mass layoffs."
        ),
        "location": "Section 9.3 — Termination Without Cause",
        "contradicted_law": "Worker Adjustment and Retraining Notification Act",
        "law_citation": "29 U.S.C. § 2102",
        "law_url1": "https://www.law.cornell.edu/uscode/text/29/2102",
        "scraped_snippet_1": (
            "An employer shall not order a plant closing or mass layoff until the end "
            "of a 60-day period after the employer serves written notice of such an "
            "order to each representative of the affected employees."
        ),
    },
    # ── misaligned_terminology × in_text ────────────────────────────────────
    {
        "source_dataset": "cuad",
        "perturb_type": "misaligned_terminology",
        "dimension": "in_text",
        "original_text": (
            "The Licensee shall not sublicense, assign, or otherwise transfer any "
            "rights under this Agreement without the prior written consent of the "
            "Licensor."
        ),
        "changed_text": (
            "The Customer shall not sublicense, assign, or otherwise transfer any "
            "rights under this Agreement without the prior written consent of the "
            "Vendor."
        ),
        "explanation": (
            "The terms 'Licensee'/'Licensor' are replaced by 'Customer'/'Vendor', "
            "which are defined differently elsewhere in the Agreement, creating "
            "terminological inconsistency and potential scope confusion."
        ),
        "location": "Section 3.4 — Assignment Restrictions",
    },
    # ── misaligned_terminology × legal ──────────────────────────────────────
    {
        "source_dataset": "nli",
        "perturb_type": "misaligned_terminology",
        "dimension": "legal",
        "original_text": (
            "The parties agree that this Agreement shall be governed by the laws of "
            "the State of Delaware, including its Uniform Commercial Code provisions."
        ),
        "changed_text": (
            "The parties agree that this Agreement shall be governed by common law "
            "principles applicable to commercial transactions in Delaware."
        ),
        "explanation": (
            "Replacing 'Uniform Commercial Code' with 'common law principles' is "
            "terminologically misaligned: Delaware has enacted the UCC (Del. Code "
            "Ann. tit. 6, § 1-101), which preempts common law for goods contracts."
        ),
        "location": "Section 14.1 — Governing Law",
        "contradicted_law": "Delaware Uniform Commercial Code",
        "law_citation": "Del. Code Ann. tit. 6, § 1-101",
        "law_url1": "https://delcode.delaware.gov/title6/c001/index.html",
        "scraped_snippet_1": (
            "This title shall be known and may be cited as the 'Uniform Commercial "
            "Code'. This title applies to transactions in goods."
        ),
    },
    # ── omission × in_text ──────────────────────────────────────────────────
    {
        "source_dataset": "cuad",
        "perturb_type": "omission",
        "dimension": "in_text",
        "original_text": (
            "Either party may terminate this Agreement upon thirty (30) days written "
            "notice. Upon termination, the Contractor shall deliver all work product "
            "and the Client shall pay for all work performed through the termination date."
        ),
        "changed_text": (
            "Either party may terminate this Agreement upon thirty (30) days written "
            "notice."
        ),
        "explanation": (
            "The post-termination obligations — delivery of work product and pro-rata "
            "payment — have been silently removed, leaving both parties' end-of-contract "
            "duties undefined."
        ),
        "location": "Section 11.2 — Termination Consequences",
    },
    # ── omission × legal ────────────────────────────────────────────────────
    {
        "source_dataset": "nli",
        "perturb_type": "omission",
        "dimension": "legal",
        "original_text": (
            "The Processor shall implement appropriate technical and organisational "
            "measures to protect Personal Data, including encryption, access controls, "
            "and breach notification to the Controller within 72 hours of discovery."
        ),
        "changed_text": (
            "The Processor shall implement appropriate technical and organisational "
            "measures to protect Personal Data."
        ),
        "explanation": (
            "The 72-hour breach notification requirement mandated by GDPR Art. 33 has "
            "been omitted, creating non-compliance for EU data processing activities."
        ),
        "location": "Section 5.3 — Data Security",
        "contradicted_law": "General Data Protection Regulation",
        "law_citation": "GDPR Art. 33",
        "law_url1": "https://gdpr-info.eu/art-33-gdpr/",
        "scraped_snippet_1": (
            "In the case of a personal data breach, the controller shall without undue "
            "delay and, where feasible, not later than 72 hours after having become "
            "aware of it, notify the personal data breach to the supervisory authority."
        ),
    },
    # ── structural_flaw × in_text ───────────────────────────────────────────
    {
        "source_dataset": "cuad",
        "perturb_type": "structural_flaw",
        "dimension": "in_text",
        "original_text": (
            "Warranty Period means the twelve (12) month period commencing on the "
            "date of final acceptance. During the Warranty Period, Contractor warrants "
            "that the deliverables will conform to the specifications."
        ),
        "changed_text": (
            "During the Warranty Period, Contractor warrants that the deliverables "
            "will conform to the specifications. Warranty Period means the twelve (12) "
            "month period commencing on the date of final acceptance."
        ),
        "explanation": (
            "The definition of 'Warranty Period' now appears after its first use, "
            "creating a forward-reference structural flaw that impairs readability "
            "and legal certainty."
        ),
        "location": "Section 7.1 — Warranty",
    },
    # ── structural_flaw × legal ─────────────────────────────────────────────
    {
        "source_dataset": "nli",
        "perturb_type": "structural_flaw",
        "dimension": "legal",
        "original_text": (
            "This Agreement, including all Exhibits attached hereto, constitutes the "
            "entire agreement between the parties and supersedes all prior negotiations, "
            "representations, and understandings."
        ),
        "changed_text": (
            "This Agreement constitutes the entire agreement between the parties. "
            "Exhibit A (Statement of Work) shall govern in the event of any conflict "
            "with the main body of this Agreement. This Agreement supersedes all "
            "prior negotiations, representations, and understandings, except as "
            "otherwise provided in any Exhibit."
        ),
        "explanation": (
            "The revised integration clause is structurally flawed: it simultaneously "
            "asserts supremacy of the main body (integration clause) and supremacy of "
            "Exhibit A (conflict clause), making the hierarchy of instruments "
            "undefined — a recognised drafting defect under contract law."
        ),
        "location": "Section 15 — Entire Agreement",
        "contradicted_law": "Restatement (Second) of Contracts",
        "law_citation": "Restatement (Second) of Contracts § 209",
        "law_url1": "https://www.law.cornell.edu/wex/integration_clause",
        "scraped_snippet_1": (
            "An integrated agreement is a writing or writings constituting a final "
            "expression of one or more terms of an agreement."
        ),
    },
]

assert len(_CELL_TEMPLATES) == 10, "Must have exactly 10 cell templates."


def make_fixture_instances(n: int = 20) -> list[DiscrepancyInstance]:
    """Return n synthetic DiscrepancyInstance objects covering all 10 cells.

    Cycles through the 10 (perturb_type × dimension) combinations if n > 10.
    All text is entirely fictional and suitable for unit tests and smoke tests
    without the real CLAUSE dataset.

    Parameters
    ----------
    n:
        Number of instances to generate.

    Returns
    -------
    list[DiscrepancyInstance]
        Synthetic instances with valid schema.
    """
    instances: list[DiscrepancyInstance] = []
    for i in range(n):
        template = dict(_CELL_TEMPLATES[i % len(_CELL_TEMPLATES)])
        # Make instance_id unique across cycles.
        cycle = i // len(_CELL_TEMPLATES)
        cell_idx = i % len(_CELL_TEMPLATES)
        template["instance_id"] = f"fixture-c{cycle:02d}-{cell_idx:02d}"
        # Append a cycle suffix to texts so each instance is textually distinct.
        if cycle > 0:
            template["original_text"] = template["original_text"] + f" [variant {cycle}]"
            template["changed_text"] = template["changed_text"] + f" [variant {cycle}]"
        instances.append(DiscrepancyInstance(**template))
    return instances
