from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


PerturbType = Literal[
    "ambiguity",
    "inconsistency",
    "misaligned_terminology",
    "omission",
    "structural_flaw",
]

Dimension = Literal["in_text", "legal"]


class DiscrepancyInstance(BaseModel):
    instance_id: str
    source_dataset: Literal["cuad", "nli"]
    perturb_type: PerturbType
    dimension: Dimension

    original_text: str
    changed_text: str

    explanation: str | None = None
    justification: str | None = None

    location: str | None = None
    contradicted_location: str | None = None
    contradicted_text: str | None = None

    contradicted_law: str | None = None
    law_citation: str | None = None
    law_url1: str | None = None
    law_url2: str | None = None
    scraped_snippet_1: str | None = None
    scraped_snippet_2: str | None = None

    gold_label: bool = True


class EvalRow(BaseModel):
    eval_id: str
    instance_id: str
    source_dataset: str
    perturb_type: str
    dimension: str
    task: str
    doc: str
    label: int | str | dict
    variant: str | None = None
    metadata: dict = Field(default_factory=dict)


class PredictionRow(BaseModel):
    eval_id: str
    instance_id: str
    source_dataset: str
    perturb_type: str
    dimension: str
    task: str
    label: int | str | dict
    prediction: int | str | dict | None
    raw_response: str
    parse_error: str | None = None
    variant: str | None = None
    metadata: dict = Field(default_factory=dict)
