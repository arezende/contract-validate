"""
Normative Intermediate Representation (RIN) schema for ContractFOL v3.

The RIN is a structured, auditable representation of normative elements
extracted from contract clauses, expressed in a textual first-order logic
(FOL) predicate notation. It bridges raw contract text and formal reasoning.

Predicate notation convention
------------------------------
All ``predicate_form`` values should follow this convention:

    Obrigacao(agente, acao, condicao)
        Obligation imposed on an agent to perform an action under a condition.

    Proibicao(agente, acao, condicao)
        Prohibition preventing an agent from performing an action under a condition.

    Permissao(agente, acao, condicao)
        Permission granted to an agent to perform an action under a condition.

    Prazo(evento, tempo)
        Deadline binding an event to a time constraint.

    Definicao(termo, escopo)
        Definition of a term within a given scope.

    Penalidade(agente, violacao, sancao)
        Penalty imposed on an agent for a violation, specifying the sanction.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class Symbol(BaseModel):
    """A named symbol used in the RIN predicate forms."""

    name: str
    kind: Literal["type", "predicate", "function", "constant"]
    informal_meaning: str  # mandatory annotation — auditability à la VERUS-LM

    @field_validator("name")
    @classmethod
    def name_must_be_valid_identifier(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(
                f"Symbol name {v!r} is not a valid Python identifier. "
                "Names must consist of letters, digits, and underscores, "
                "and must not start with a digit."
            )
        return v


class NormElement(BaseModel):
    """A single normative element extracted from a contract clause."""

    element_id: str
    source_clause: str  # text of the originating clause
    location: Optional[str] = None  # to align with Eval_3
    kind: Literal[
        "obligation",
        "prohibition",
        "permission",
        "definition",
        "deadline",
        "cross_reference",
    ]
    deontic_force: Optional[Literal["mandatory", "discretionary"]] = None
    predicate_form: str  # textual FOL form: Obrigacao(...), Prazo(...), etc.

    @field_validator("element_id")
    @classmethod
    def element_id_must_be_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("element_id must be a non-empty string.")
        return v


class RIN(BaseModel):
    """
    Normative Intermediate Representation — the core data structure of
    ContractFOL v3.

    Each RIN instance captures the normative content of one contract variant
    (original or changed) as produced by a specific translator model.
    """

    instance_id: str
    variant: Literal["original", "changed"]
    symbols: list[Symbol]
    elements: list[NormElement]
    translator_model: str  # which LLM generated it — for H₂ tracing

    @field_validator("elements")
    @classmethod
    def elements_must_not_be_empty(cls, v: list[NormElement]) -> list[NormElement]:
        if not v:
            raise ValueError(
                "A RIN must contain at least one NormElement. "
                "An empty elements list indicates a translation failure."
            )
        return v

    def to_jsonl_line(self) -> str:
        """Serialize to a single JSON line (for .jsonl files)."""
        return self.model_dump_json()

    @classmethod
    def from_jsonl_line(cls, line: str) -> "RIN":
        """Deserialize from a single JSON line."""
        return cls.model_validate(json.loads(line))
