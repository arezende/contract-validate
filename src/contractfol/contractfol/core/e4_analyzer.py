"""E4 — Análise Formal: 6 verificações (V1-V6)."""

import time
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from z3 import *

from contractfol.contractfol.models import (
    ClausulaEstruturada,
    Extracao,
    Problema,
    ResultadoAnalise,
    Severidade,
    TipoProblema,
)

console = Console()


def analisar_contrato(
    nome_contrato: str,
    extracao: Extracao,
    solver: Solver,
) -> ResultadoAnalise:
    """E4: Executa 6 verificações formais."""
    console.print(f"\n🔍 E4 — Análise Formal: {nome_contrato}")

    inicio = time.time()
    problemas = []

    # V1 — Consistência geral
    console.print("  V1 Consistência geral...", end=" ")
    resultado_v1 = solver.check()
    if resultado_v1 == unsat:
        core = solver.unsat_core()
        clausulas_core = [str(c) for c in core][:5]
        problemas.append(
            Problema(
                tipo=TipoProblema.CONTRADICAO,
                severidade=Severidade.CRITICA,
                clausulas=clausulas_core,
                descricao="Contradição formal detectada pelo solver Z3",
                evidencia_formal=f"UNSAT core: {', '.join(clausulas_core)}",
            )
        )
        console.print("❌ UNSAT")
    else:
        console.print("✅ SAT")

    # V2 — Contradições deônticas (obrigação + proibição)
    console.print("  V2 Contradições deônticas...", end=" ")
    pares_conflito = []
    for ce1 in extracao.clausulas:
        for ce2 in extracao.clausulas:
            if ce1.clausula_id < ce2.clausula_id and ce1.agente == ce2.agente:
                if ce1.acao.lower() == ce2.acao.lower() or ce1.acao.lower() in ce2.acao.lower():
                    if (ce1.tipo_deontico.value == "obrigacao" and ce2.tipo_deontico.value == "proibicao") or \
                       (ce1.tipo_deontico.value == "proibicao" and ce2.tipo_deontico.value == "obrigacao"):
                        pares_conflito.append((ce1.clausula_id, ce2.clausula_id))

    if pares_conflito:
        for cl1, cl2 in pares_conflito:
            problemas.append(
                Problema(
                    tipo=TipoProblema.PROIBICAO_CONFLITA_OBRIGACAO,
                    severidade=Severidade.CRITICA,
                    clausulas=[cl1, cl2],
                    descricao=f"{cl1} e {cl2} com modalidades conflitantes",
                    sugestao="Harmonizar as duas cláusulas",
                )
            )
        console.print(f"❌ {len(pares_conflito)} conflito(s)")
    else:
        console.print("✅ OK")

    # V3 — Inconsistência de prazos
    console.print("  V3 Consistência de prazos...", end=" ")
    prazos_conflito = []
    for ce1 in extracao.clausulas:
        if ce1.prazo:
            for ce2 in extracao.clausulas:
                if ce2.prazo and ce1.clausula_id != ce2.clausula_id:
                    if ce1.prazo.valor > ce2.prazo.valor * 2:
                        if "prazo" in ce1.acao.lower() and "prazo" in ce2.acao.lower():
                            prazos_conflito.append((ce1.clausula_id, ce2.clausula_id))

    if prazos_conflito:
        for cl1, cl2 in prazos_conflito:
            problemas.append(
                Problema(
                    tipo=TipoProblema.INCONSISTENCIA_PRAZO,
                    severidade=Severidade.ALTA,
                    clausulas=[cl1, cl2],
                    descricao=f"Prazos inconsistentes: {cl1} vs {cl2}",
                    sugestao="Alinhar prazos entre cláusulas relacionadas",
                )
            )
        console.print(f"⚠️  {len(prazos_conflito)} alerta(s)")
    else:
        console.print("✅ OK")

    # V4 — Cobertura de penalidades
    console.print("  V4 Cobertura de penalidades...", end=" ")
    obrigacoes = [ce for ce in extracao.clausulas if ce.tipo_deontico.value == "obrigacao"]
    obrigacoes_sem_penalidade = [
        ce for ce in obrigacoes if not ce.penalidade_ref and ce.clausula_id not in [p.clausula_id for p in extracao.clausulas if p.tipo_deontico.value == "penalidade"]
    ]

    if obrigacoes_sem_penalidade:
        for ce in obrigacoes_sem_penalidade[:3]:
            problemas.append(
                Problema(
                    tipo=TipoProblema.LACUNA_PENALIDADE,
                    severidade=Severidade.MEDIA,
                    clausulas=[ce.clausula_id],
                    descricao=f"{ce.clausula_id}: obrigação sem penalidade associada",
                    sugestao="Adicionar cláusula de penalidade para esta obrigação",
                )
            )
        console.print(f"🟡 {len(obrigacoes_sem_penalidade)} sem penalidade")
    else:
        console.print("✅ OK")

    # V5 — Completude de prazos
    console.print("  V5 Completude de prazos...", end=" ")
    obrigacoes_sem_prazo = [ce for ce in obrigacoes if not ce.prazo]
    if obrigacoes_sem_prazo:
        console.print(f"🟡 {len(obrigacoes_sem_prazo)} sem prazo explícito")
    else:
        console.print("✅ OK")

    # V6 — Razoabilidade
    console.print("  V6 Razoabilidade...", end=" ")
    alertas_v6 = []
    for ce in extracao.clausulas:
        if ce.prazo and ce.prazo.valor <= 0:
            alertas_v6.append((ce.clausula_id, "Prazo <= 0"))
        if ce.valor and ce.valor.montante and ce.valor.montante == 0:
            alertas_v6.append((ce.clausula_id, "Valor = 0"))

    if alertas_v6:
        for cl, msg in alertas_v6:
            problemas.append(
                Problema(
                    tipo=TipoProblema.PRAZO_IRRAZOAVEL,
                    severidade=Severidade.BAIXA,
                    clausulas=[cl],
                    descricao=msg,
                )
            )
        console.print(f"🟡 {len(alertas_v6)} alerta(s)")
    else:
        console.print("✅ OK")

    # Cobertura de penalidades (%)
    cobertura = (len(obrigacoes) - len(obrigacoes_sem_penalidade)) / len(obrigacoes) if obrigacoes else 1.0

    tempo_ms = (time.time() - inicio) * 1000

    resultado = ResultadoAnalise(
        contrato=nome_contrato,
        total_clausulas=len(extracao.clausulas),
        total_problemas=len(problemas),
        problemas=problemas,
        mapa_deontico=extracao.mapa_deontico,
        cobertura_penalidades=round(cobertura, 2),
        tempo_ms=round(tempo_ms, 1),
    )

    # Validação E4
    _imprimir_validacao_e4(resultado)
    return resultado


def _imprimir_validacao_e4(analise: ResultadoAnalise):
    """Imprime saída formatada de E4."""
    if not analise.problemas:
        console.print("\n✅ [green]NENHUM PROBLEMA DETECTADO[/green]\n")
        return

    table = Table(title="🔴 Problemas Detectados", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("Tipo", width=20)
    table.add_column("Severidade", width=10)
    table.add_column("Cláusulas", width=15)
    table.add_column("Descrição", width=40)

    for i, p in enumerate(analise.problemas, 1):
        sev_cor = {"critica": "red", "alta": "yellow", "media": "yellow", "baixa": "dim", "info": "white"}
        sev = f"[{sev_cor.get(p.severidade.value, 'white')}]{p.severidade.value}[/{sev_cor.get(p.severidade.value, 'white')}]"
        table.add_row(
            str(i),
            p.tipo.value[:20],
            sev,
            ", ".join(p.clausulas),
            p.descricao[:40],
        )

    console.print(table)
    console.print(f"\n  Total: {analise.total_problemas} problemas")
    console.print(f"  Cobertura penalidades: {analise.cobertura_penalidades:.0%}")
    console.print(f"  Tempo: {analise.tempo_ms:.0f}ms\n")
