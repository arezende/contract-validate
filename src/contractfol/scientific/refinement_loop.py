"""Simple refinement loop for the scientific pipeline."""

from __future__ import annotations

from .models import FormulaFOL


def selecionar_estrategia_refinada(formula: FormulaFOL, tentativa: int) -> str:
    if formula.confianca >= 0.85:
        return "few_shot"
    if tentativa == 1:
        return "few_shot"
    if tentativa == 2:
        return "cot"
    return "composicional"
