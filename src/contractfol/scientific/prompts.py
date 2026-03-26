"""Prompt builders for NL -> FOL translation."""

from __future__ import annotations

import json
from typing import Tuple


SYSTEM_PROMPT_BASE = """You are a specialist in Brazilian contract logic.

Translate one contractual clause into First-Order Logic JSON only.

Return valid JSON with:
{type_deontic, quantifier, antecedent, consequent, formula_fol, codigo_z3, confianca, ambiguidades}
"""


FEW_SHOT_EXAMPLES = [
    {
        "input": "O COB deverá repassar os recursos em ate 30 dias.",
        "output": {
            "tipo_deontico": "obrigacao",
            "quantificador": "universal",
            "antecedente": [],
            "consequente": [
                {
                    "predicado": "Obrigacao",
                    "argumentos": ["COB", "RepassarRecursos", "30"],
                    "negado": False,
                }
            ],
            "formula_fol": "Obrigacao(COB, RepassarRecursos, 30)",
            "codigo_z3": "And(Obrigacao_COB_RepassarRecursos, prazo_repassar_recursos == 30)",
            "confianca": 0.95,
            "ambiguidades": [],
        },
    }
]


def build_prompt_traducao(texto_clausula: str, estrategia: str = "few_shot") -> Tuple[str, str]:
    if estrategia == "zero_shot":
        return SYSTEM_PROMPT_BASE, f"Clause: {texto_clausula}\nReturn JSON only."

    if estrategia == "few_shot":
        exemplos = "\n\n".join(
            f"Example {i + 1}:\nInput: {ex['input']}\nOutput: {json.dumps(ex['output'], ensure_ascii=False)}"
            for i, ex in enumerate(FEW_SHOT_EXAMPLES)
        )
        return (
            SYSTEM_PROMPT_BASE + "\n\n" + exemplos,
            f"Clause: {texto_clausula}\nReturn JSON only.",
        )

    if estrategia == "cot":
        return (
            SYSTEM_PROMPT_BASE + "\nReason silently and return the final JSON only.",
            f"Clause: {texto_clausula}\nReturn JSON only.",
        )

    if estrategia == "composicional":
        return (
            SYSTEM_PROMPT_BASE
            + "\nDecompose complex clauses if needed, but return a single JSON object.",
            f"Clause: {texto_clausula}\nReturn JSON only.",
        )

    raise ValueError(f"Estrategia nao suportada: {estrategia}")
