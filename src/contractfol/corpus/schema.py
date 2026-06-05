"""DiscrepancyInstance — canonical schema for ContractFOL corpus instances."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Dimension = Literal["in_text", "legal"]
PerturbType = Literal[
    "ambiguity",
    "inconsistency",
    "misaligned_terminology",
    "omission",
    "structural_flaw",
]


class DiscrepancyInstance(BaseModel):
    instance_id: str
    source_dataset: Literal["cuad", "nli"]
    perturb_type: PerturbType
    dimension: Dimension
    original_text: str               # consistent contract — calibration control
    changed_text: str                # perturbed contract — test
    explanation: str                 # GT justification (NEVER use to build KB)
    location: Optional[str] = None
    contradicted_location: Optional[str] = None
    contradicted_text: Optional[str] = None
    # legal dimension only:
    contradicted_law: Optional[str] = None
    law_citation: Optional[str] = None
    law_url1: Optional[str] = None
    law_url2: Optional[str] = None
    scraped_snippet_1: Optional[str] = None   # statute text — legitimate KB source
    scraped_snippet_2: Optional[str] = None
    gold_label: bool = True          # ground truth by construction
