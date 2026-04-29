"""E5 — Relatório: Terminal + Markdown export."""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from contractfol.contractfol.config import REPORTS_DIR
from contractfol.contractfol.models import (
    Extracao,
    LinhaRelatorio,
    Relatorio,
    ResultadoAnalise,
)

console = Console()


def gerar_relatorio(
    nome_contrato: str,
    analise: ResultadoAnalise,
    extracao: Extracao,
) -> Relatorio:
    """E5: Gera relatório em terminal + Markdown."""
    console.print(f"\n📋 E5 — Geração de Relatório")

    # Criar linhas do relatório
    linhas = []
    for ce in extracao.clausulas:
        # Determinar status
        problemas_clausula = [p for p in analise.problemas if ce.clausula_id in p.clausulas]
        if problemas_clausula:
            status = "🔴 erro" if any(p.severidade.value == "critica" for p in problemas_clausula) else "⚠️  alert"
            detalhe = problemas_clausula[0].descricao
        elif ce.confianca < 0.7:
            status = "⚠️  alert"
            detalhe = f"Ambígua (conf: {ce.confianca:.0%})"
        else:
            status = "✅ ok"
            detalhe = "Sem problemas"

        linhas.append(
            LinhaRelatorio(
                clausula_id=ce.clausula_id,
                tipo=ce.tipo_deontico.value,
                agente=ce.agente,
                status=status,
                detalhe=detalhe,
            )
        )

    # Resumo
    total_ok = sum(1 for l in linhas if "✅" in l.status)
    total_alert = sum(1 for l in linhas if "⚠️" in l.status)
    total_erro = sum(1 for l in linhas if "🔴" in l.status)
    resumo = (
        f"Analisadas {len(linhas)} cláusulas. "
        f"{total_ok} OK, {total_alert} alertas, {total_erro} erros. "
        f"Cobertura penalidades: {analise.cobertura_penalidades:.0%}"
    )

    relatorio = Relatorio(
        titulo="Relatório de Análise Contratual — ContractFOL V3",
        data=datetime.now().strftime("%Y-%m-%d %H:%M"),
        contrato=nome_contrato,
        resumo=resumo,
        linhas=linhas,
        problemas=analise.problemas,
        estatisticas={
            "total_clausulas": analise.total_clausulas,
            "total_problemas": analise.total_problemas,
            "cobertura_penalidades": analise.cobertura_penalidades,
            "tempo_ms": analise.tempo_ms,
        },
    )

    # Validação E5
    _imprimir_validacao_e5(relatorio)
    _exportar_markdown(relatorio, extracao)
    return relatorio


def _imprimir_validacao_e5(rel: Relatorio):
    """Imprime saída formatada de E5."""
    console.print(
        Panel(
            f"{rel.titulo}\n\n"
            f"Contrato: {rel.contrato}\n"
            f"Data: {rel.data}\n\n"
            f"[italic]{rel.resumo}[/italic]",
            title="📋 E5 — Relatório",
            border_style="magenta",
        )
    )

    # Tabela de cláusulas
    table = Table(show_lines=True)
    table.add_column("ID", style="bold", width=10)
    table.add_column("Tipo", width=12)
    table.add_column("Agente", width=15)
    table.add_column("Status", width=10)
    table.add_column("Detalhe", width=40)

    for linha in rel.linhas:
        table.add_row(
            linha.clausula_id,
            linha.tipo[:12],
            linha.agente[:15],
            linha.status,
            linha.detalhe[:40],
        )

    console.print(table)
    console.print()


def _exportar_markdown(rel: Relatorio, extracao: Extracao):
    """Exporta relatório como Markdown com notação deôntica e FOL para cláusulas problemáticas."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = REPORTS_DIR / f"relatorio_{ts}.md"

    conteudo = f"""# {rel.titulo}

**Contrato:** {rel.contrato}
**Data:** {rel.data}

## Resumo

{rel.resumo}

## Análise por Cláusula

| ID | Tipo | Agente | Status | Detalhe |
|---|---|---|---|---|
"""

    for linha in rel.linhas:
        conteudo += f"| {linha.clausula_id} | {linha.tipo} | {linha.agente} | {linha.status} | {linha.detalhe} |\n"

    if rel.problemas:
        conteudo += f"\n## Problemas Detectados ({len(rel.problemas)})\n\n"

        # Mapear cláusulas extraídas por ID para acesso rápido
        mapa_clausulas = {ce.clausula_id: ce for ce in extracao.clausulas}

        for i, p in enumerate(rel.problemas, 1):
            conteudo += (
                f"### {i}. {p.tipo.value.upper()} ({p.severidade.value})\n\n"
                f"**Cláusulas afetadas:** {', '.join(p.clausulas)}\n\n"
                f"**Descrição:** {p.descricao}\n\n"
            )

            # Adicionar notação deôntica e FOL para cada cláusula com problema
            for clausula_id in p.clausulas:
                if clausula_id in mapa_clausulas:
                    ce = mapa_clausulas[clausula_id]
                    conteudo += f"**{clausula_id}:**\n\n"

                    # Notação deôntica
                    conteudo += f"- **Tipo deôntico:** `{ce.tipo_deontico.value}`\n"
                    conteudo += f"- **Agente:** `{ce.agente or '—'}`\n"
                    conteudo += f"- **Ação:** `{ce.acao}`\n"
                    if ce.objeto:
                        conteudo += f"- **Objeto:** `{ce.objeto}`\n"
                    if ce.condicao:
                        conteudo += f"- **Condição:** `{ce.condicao}`\n"
                    if ce.prazo:
                        conteudo += f"- **Prazo:** `{ce.prazo.valor} {ce.prazo.unidade}`\n"
                    conteudo += f"- **Confiança:** `{ce.confianca:.0%}`\n\n"

                    # Fórmula FOL
                    conteudo += f"**Fórmula em Primeira Ordem (FOL):**\n\n"
                    conteudo += f"```\n{ce.formula_fol}\n```\n\n"

                    # Código Z3
                    conteudo += f"**Código Z3 (SMT Solver):**\n\n"
                    conteudo += f"```python\n{ce.codigo_z3}\n```\n\n"

            if p.sugestao:
                conteudo += f"**💡 Sugestão:** {p.sugestao}\n\n"
            conteudo += "\n"

    conteudo += f"""## Estatísticas

- Total de cláusulas: {rel.estatisticas['total_clausulas']}
- Problemas: {rel.estatisticas['total_problemas']}
- Cobertura penalidades: {rel.estatisticas['cobertura_penalidades']:.0%}
- Tempo: {rel.estatisticas['tempo_ms']:.0f}ms
"""

    caminho.write_text(conteudo, encoding="utf-8")
    console.print(f"  📄 Exportado: {caminho}\n")
