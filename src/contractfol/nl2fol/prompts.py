"""
Generic prompt assembly for the NL → FOL translation pipeline.

These prompts are intentionally domain-agnostic: they explain FOL vocabulary
and normative element kinds using fictional non-CLAUSE examples. No examples
are drawn from the CLAUSE dataset or perturbation types.
"""

from __future__ import annotations

import json


_SYMBOL_EXAMPLE_CLAUSE = (
    "The lessor shall maintain the leased premises in good repair throughout the lease term."
)

_SYMBOL_EXAMPLE_OUTPUT = json.dumps(
    [
        {
            "name": "Lessor",
            "kind": "constant",
            "informal_meaning": "The party who grants the lease (landlord).",
        },
        {
            "name": "LeasedPremises",
            "kind": "constant",
            "informal_meaning": "The physical property subject to the lease.",
        },
        {
            "name": "maintain_good_repair",
            "kind": "predicate",
            "informal_meaning": "The action of keeping the premises in an acceptable state of repair.",
        },
        {
            "name": "LeaseTerm",
            "kind": "constant",
            "informal_meaning": "The duration of the lease agreement.",
        },
    ],
    indent=2,
)

_FORMULA_EXAMPLE_OUTPUT = json.dumps(
    [
        {
            "element_id": "e1",
            "source_clause": "The lessor shall maintain the leased premises in good repair throughout the lease term.",
            "location": None,
            "kind": "obligation",
            "deontic_force": "mandatory",
            "predicate_form": "Obrigacao(Lessor, maintain_good_repair, during_LeaseTerm)",
        }
    ],
    indent=2,
)


def symbol_extraction_prompt(clause_text: str) -> str:
    """
    Returns the prompt for Step 4.1: asking the LLM to identify
    types, predicates, functions, and constants in the clause text
    and annotate each with its informal meaning.
    """
    return f"""You are a legal-logic analyst. Your task is to identify the formal vocabulary
(symbols) needed to represent the following contract clause in First-Order Logic (FOL).

CONTRACT CLAUSE:
\"\"\"{clause_text}\"\"\"

SYMBOL KINDS
------------
Identify every meaningful symbol in the clause and classify it into one of these four kinds:

1. type       — A set or sort of entities (e.g., Party, Document, Date).
2. predicate  — A relation or property that can be true or false of entities
                (e.g., delivered(x), in_good_repair(x)).
3. function   — A mapping from entities to another entity
                (e.g., due_date(contract), amount_owed(party)).
4. constant   — A specific named individual or value in the domain
                (e.g., Buyer, ContractDate, 30).

ANNOTATION RULE
---------------
For every symbol you identify, provide its informal meaning: a short English
phrase that explains what the symbol represents in the context of the clause.
This annotation is mandatory for auditability.

OUTPUT FORMAT
-------------
Return ONLY a JSON array with no additional prose. Each item must have exactly
these three keys:

  "name"             — valid identifier (letters, digits, underscores; not starting with a digit)
  "kind"             — one of: "type", "predicate", "function", "constant"
  "informal_meaning" — short English description

GENERIC EXAMPLE
---------------
Clause: "{_SYMBOL_EXAMPLE_CLAUSE}"

Output:
{_SYMBOL_EXAMPLE_OUTPUT}

Now extract symbols for the CONTRACT CLAUSE above. Return ONLY the JSON array.
"""


def formula_extraction_prompt(clause_text: str, symbols: list[dict]) -> str:
    """
    Returns the prompt for Step 4.2: given the symbol vocabulary
    from Step 4.1, asking the LLM to extract NormElements as FOL
    predicate forms.

    symbols: list of {{"name": str, "kind": str, "informal_meaning": str}}
    """
    symbols_json = json.dumps(symbols, indent=2)

    return f"""You are a legal-logic analyst. Your task is to extract every normative element
from the following contract clause and express each one as a predicate-form
statement in First-Order Logic (FOL), using the symbol vocabulary provided.

CONTRACT CLAUSE:
\"\"\"{clause_text}\"\"\"

SYMBOL VOCABULARY:
{symbols_json}

NORMATIVE ELEMENT KINDS
------------------------
Express each normative element using one of these six predicate signatures:

  Obrigacao(agente, acao, condicao)
      An obligation imposed on an agent to perform an action under a condition.

  Proibicao(agente, acao, condicao)
      A prohibition preventing an agent from performing an action under a condition.

  Permissao(agente, acao, condicao)
      A permission granted to an agent to perform an action under a condition.

  Prazo(evento, tempo)
      A deadline binding an event to a time constraint.

  Definicao(termo, escopo)
      A definition of a term within a given scope.

  Penalidade(agente, violacao, sancao)
      A penalty imposed on an agent for a violation, specifying the sanction.

EXTRACTION RULES
----------------
- Identify every distinct normative obligation, prohibition, permission,
  deadline, definition, or penalty expressed (explicitly or implicitly)
  in the clause.
- Use symbol names from the vocabulary above when they apply.
- Assign a unique element_id to each element (e.g., "e1", "e2", …).
- Set deontic_force to "mandatory" when the clause uses imperative language
  ("shall", "must", "will not") or "discretionary" for permissive language
  ("may", "is permitted to"). Set to null if not applicable (e.g., definitions).
- Set location to the verbatim sub-string of the clause that supports this
  element, or null if the element spans the whole clause.

OUTPUT FORMAT
-------------
Return ONLY a JSON array with no additional prose. Each item must have exactly
these six keys:

  "element_id"    — unique string identifier (e.g., "e1")
  "source_clause" — the full text of the clause being analyzed
  "location"      — verbatim sub-string or null
  "kind"          — one of: "obligation", "prohibition", "permission",
                    "definition", "deadline", "cross_reference"
  "deontic_force" — "mandatory", "discretionary", or null
  "predicate_form"— the FOL predicate expression (e.g., Obrigacao(Lessor, pay, monthly))

GENERIC EXAMPLE
---------------
Clause: "{_SYMBOL_EXAMPLE_CLAUSE}"

Symbol vocabulary (abbreviated):
[
  {{"name": "Lessor", "kind": "constant", "informal_meaning": "The party who grants the lease."}},
  {{"name": "maintain_good_repair", "kind": "predicate", "informal_meaning": "Keeping premises in acceptable repair."}}
]

Output:
{_FORMULA_EXAMPLE_OUTPUT}

Now extract normative elements for the CONTRACT CLAUSE above. Return ONLY the JSON array.
"""
