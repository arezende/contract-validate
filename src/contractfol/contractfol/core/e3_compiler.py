"""E3 — Compilação Z3: Executa código Z3 de cada cláusula."""

from typing import List

from rich.console import Console
from z3 import *

from contractfol.contractfol.models import (
    ClausulaEstruturada,
    Extracao,
    FormulaCompilada,
)

console = Console()


def compilar_extracao(extracao: Extracao) -> tuple[Solver, List[FormulaCompilada], dict]:
    """E3: Compila todas as cláusulas para Z3 e retorna Solver global."""
    console.print(f"\n⚙️  E3 — Compilação Z3: {len(extracao.clausulas)} cláusulas")

    solver = Solver()
    solver.set("timeout", 30000)

    formulas_compiladas = []
    namespace = {"s": solver, "Bool": Bool, "Int": Int, "And": And, "Or": Or, "Not": Not, "Implies": Implies, "ForAll": ForAll, "Exists": Exists}

    for ce in extracao.clausulas:
        try:
            exec(ce.codigo_z3, namespace)
            formulas_compiladas.append(
                FormulaCompilada(clausula_id=ce.clausula_id, expressao_z3=ce.codigo_z3, compilou=True)
            )
            console.print(f"  ✅ {ce.clausula_id}")
        except Exception as e:
            formulas_compiladas.append(
                FormulaCompilada(clausula_id=ce.clausula_id, expressao_z3=None, compilou=False, erro=str(e))
            )
            console.print(f"  ❌ {ce.clausula_id}: {str(e)[:40]}")

    total_compiladas = sum(1 for f in formulas_compiladas if f.compilou)
    console.print(f"\n  Compiladas: {total_compiladas}/{len(formulas_compiladas)}\n")

    return solver, formulas_compiladas, namespace
