"""Main — Orquestrador do pipeline ContractFOL V3 com processamento em lote."""

import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import os
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")

from contractfol.contractfol.config import INPUT_DIR, OUTPUT_DIR
from contractfol.contractfol.core.e1_preprocessor import preprocessar
from contractfol.contractfol.core.e2_extractor import extrair_contrato
from contractfol.contractfol.core.e3_compiler import compilar_extracao
from contractfol.contractfol.core.e4_analyzer import analisar_contrato
from contractfol.contractfol.core.e5_reporter import gerar_relatorio

console = Console(force_terminal=True, legacy_windows=False)


def _serializar_e1(contrato_segmentado) -> dict:
    """Serializa saída E1 para JSON."""
    return {
        "arquivo": contrato_segmentado.arquivo,
        "titulo": contrato_segmentado.titulo,
        "partes": contrato_segmentado.partes,
        "contratante": contrato_segmentado.partes[0] if contrato_segmentado.partes else "Desconhecido",
        "contratado": contrato_segmentado.partes[1] if len(contrato_segmentado.partes) > 1 else "Desconhecido",
        "clausulas": [
            {
                "id": c.id,
                "numero": c.numero,
                "secao": c.secao,
                "texto": c.texto,
            }
            for c in contrato_segmentado.clausulas
        ],
        "total_clausulas": len(contrato_segmentado.clausulas),
    }


def _serializar_e2(extracao) -> dict:
    """Serializa saída E2 para JSON."""
    return {
        "clausulas": [
            {
                "id": ce.clausula_id,
                "tipo_deontico": ce.tipo_deontico.value,
                "agente": ce.agente,
                "acao": ce.acao,
                "objeto": ce.objeto,
                "condicao": ce.condicao,
                "prazo": {
                    "valor": ce.prazo.valor,
                    "unidade": ce.prazo.unidade,
                } if ce.prazo else None,
                "valor": {
                    "montante": ce.valor.montante,
                    "descricao": ce.valor.descricao,
                } if ce.valor else None,
                "penalidade_ref": ce.penalidade_ref,
                "confianca": float(ce.confianca),
                "ambiguidades": ce.ambiguidades,
            }
            for ce in extracao.clausulas
        ],
        "mapa_deontico": extracao.mapa_deontico,
        "confianca_media": sum(c.confianca for c in extracao.clausulas) / len(extracao.clausulas) if extracao.clausulas else 0,
    }


def _serializar_e4(analise) -> dict:
    """Serializa saída E4 para JSON."""
    return {
        "problemas": [
            {
                "tipo": p.tipo.value,
                "severidade": p.severidade.value,
                "clausulas": p.clausulas,
                "descricao": p.descricao,
                "sugestao": p.sugestao,
            }
            for p in analise.problemas
        ],
        "total_problemas": analise.total_problemas,
        "cobertura_penalidades": float(analise.cobertura_penalidades),
        "tempo_ms": analise.tempo_ms,
    }


def _serializar_mapa_deontico(extracao) -> dict:
    """Serializa mapeamento deôntico com rastreabilidade às cláusulas originais."""
    mapa = {}

    for clausula in extracao.clausulas:
        tipo = clausula.tipo_deontico.value
        agente = clausula.agente or "—"

        # Chave: tipo_deontico + agente
        chave = f"{tipo}_{agente.replace(' ', '_').replace('.', '')}"

        if chave not in mapa:
            mapa[chave] = {
                "tipo_deontico": tipo,
                "agente": agente,
                "sentencas": []
            }

        # Adicionar sentença deôntica com rastreabilidade
        mapa[chave]["sentencas"].append({
            "clausula_id": clausula.clausula_id,
            "texto_original": clausula.texto_original,
            "acao": clausula.acao,
            "objeto": clausula.objeto,
            "condicao": clausula.condicao,
            "confianca": float(clausula.confianca),
            "prazo": {
                "valor": clausula.prazo.valor,
                "unidade": clausula.prazo.unidade,
            } if clausula.prazo else None,
            "valor": {
                "montante": clausula.valor.montante,
                "descricao": clausula.valor.descricao,
            } if clausula.valor else None,
        })

    return mapa


def _serializar_formulas_fol(extracao) -> dict:
    """Serializa fórmulas FOL com rastreabilidade às cláusulas originais."""
    return {
        "formulas": [
            {
                "clausula_id": ce.clausula_id,
                "texto_original": ce.texto_original,
                "tipo_deontico": ce.tipo_deontico.value,
                "agente": ce.agente,
                "acao": ce.acao,
                "objeto": ce.objeto,
                "condicao": ce.condicao,
                "formula_fol": ce.formula_fol,
                "codigo_z3": ce.codigo_z3,
                "confianca": float(ce.confianca),
                "ambiguidades": ce.ambiguidades,
            }
            for ce in extracao.clausulas
        ],
        "total_formulas": len(extracao.clausulas),
    }


def salvar_saidas(nome_contrato: str, contrato_segmentado, extracao, formulas_compiladas, analise, relatorio):
    """Salva as saídas de cada etapa em JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Criar pastas de saída por etapa
    for etapa in ["E1", "E2", "E3", "E4", "E5", "MAPA_DEONTICO", "FOL"]:
        (OUTPUT_DIR / etapa).mkdir(parents=True, exist_ok=True)

    # E1
    e1_saida = {
        "timestamp": timestamp,
        "etapa": "E1 — Pré-processamento",
        **_serializar_e1(contrato_segmentado)
    }
    e1_path = OUTPUT_DIR / "E1" / f"contrato_E1_{nome_contrato}.json"
    e1_path.write_text(json.dumps(e1_saida, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 E1: {e1_path.name}")

    # E2
    e2_saida = {
        "timestamp": timestamp,
        "etapa": "E2 — Extração Estruturada",
        **_serializar_e2(extracao)
    }
    e2_path = OUTPUT_DIR / "E2" / f"contrato_E2_{nome_contrato}.json"
    e2_path.write_text(json.dumps(e2_saida, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 E2: {e2_path.name}")

    # MAPA DEÔNTICO (com rastreabilidade)
    mapa_deontico = {
        "timestamp": timestamp,
        "contrato": nome_contrato,
        "descricao": "Mapeamento deôntico com rastreabilidade às cláusulas originais",
        "mapa": _serializar_mapa_deontico(extracao)
    }
    mapa_path = OUTPUT_DIR / "MAPA_DEONTICO" / f"mapa_deontico_{nome_contrato}.json"
    mapa_path.write_text(json.dumps(mapa_deontico, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 Mapa Deôntico: {mapa_path.name}")

    # FÓRMULAS FOL (tradução para primeira ordem)
    formulas_fol = {
        "timestamp": timestamp,
        "contrato": nome_contrato,
        "descricao": "Fórmulas FOL com rastreabilidade às cláusulas originais",
        **_serializar_formulas_fol(extracao)
    }
    fol_path = OUTPUT_DIR / "FOL" / f"formulas_fol_{nome_contrato}.json"
    fol_path.write_text(json.dumps(formulas_fol, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 Fórmulas FOL: {fol_path.name}")

    # E3
    e3_saida = {
        "timestamp": timestamp,
        "etapa": "E3 — Compilação Z3",
        "total_formulas": len(formulas_compiladas),
        "compiladas": sum(1 for f in formulas_compiladas if f.compilou),
        "taxa_compilacao": sum(1 for f in formulas_compiladas if f.compilou) / len(formulas_compiladas) if formulas_compiladas else 0,
    }
    e3_path = OUTPUT_DIR / "E3" / f"contrato_E3_{nome_contrato}.json"
    e3_path.write_text(json.dumps(e3_saida, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 E3: {e3_path.name}")

    # E4
    e4_saida = {
        "timestamp": timestamp,
        "etapa": "E4 — Análise Formal",
        **_serializar_e4(analise)
    }
    e4_path = OUTPUT_DIR / "E4" / f"contrato_E4_{nome_contrato}.json"
    e4_path.write_text(json.dumps(e4_saida, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  💾 E4: {e4_path.name}")

    # E5 (Markdown já é gerado)
    console.print(f"  💾 E5: relatorio_*.md")


def processar_contratos():
    """Processa todos os contratos da pasta input."""
    console.print(
        Panel(
            "[bold]ContractFOL V3 — Processamento em Lote[/bold]\n"
            f"Pasta: {INPUT_DIR}\n",
            title="🚀 Início",
            border_style="bold blue",
        )
    )

    # Encontrar contratos
    padroes = ["*.txt", "*.docx", "*.pdf"]
    contratos = []
    for padrao in padroes:
        contratos.extend(INPUT_DIR.glob(padrao))

    if not contratos:
        console.print(f"[yellow]⚠️  Nenhum contrato encontrado em {INPUT_DIR}[/yellow]")
        return

    console.print(f"[cyan]📄 {len(contratos)} contrato(s) encontrado(s)[/cyan]\n")

    # Processar cada contrato
    resultados = []
    for i, caminho_contrato in enumerate(contratos, 1):
        console.print(
            Panel(
                f"[bold]{i}/{len(contratos)} — {caminho_contrato.name}[/bold]",
                border_style="dim",
            )
        )

        try:
            nome_stem = caminho_contrato.stem

            # E1
            contrato_segmentado = preprocessar(caminho_contrato, titulo=nome_stem)

            # E2
            extracao = extrair_contrato(contrato_segmentado)

            # E3
            solver, formulas_compiladas, namespace = compilar_extracao(extracao)

            # E4
            analise = analisar_contrato(nome_stem, extracao, solver)

            # E5
            relatorio = gerar_relatorio(nome_stem, analise, extracao)

            # Salvar saídas
            console.print("\n[cyan]Salvando saídas...[/cyan]")
            salvar_saidas(nome_stem, contrato_segmentado, extracao, formulas_compiladas, analise, relatorio)

            # Registrar resultado
            resultados.append({
                "contrato": caminho_contrato.name,
                "contratante": contrato_segmentado.partes[0] if contrato_segmentado.partes else "—",
                "contratado": contrato_segmentado.partes[1] if len(contrato_segmentado.partes) > 1 else "—",
                "clausulas": len(contrato_segmentado.clausulas),
                "confianca": f"{sum(c.confianca for c in extracao.clausulas)/len(extracao.clausulas):.0%}",
                "problemas": analise.total_problemas,
                "status": "✅",
            })

        except Exception as e:
            console.print(f"[red]❌ Erro: {str(e)[:80]}[/red]\n")
            resultados.append({
                "contrato": caminho_contrato.name,
                "status": "❌ Erro",
                "erro": str(e)[:100],
            })

    # Gerar arquivo de índice geral
    indice = {
        "data_processamento": datetime.now().isoformat(),
        "total_contratos": len(resultados),
        "contratos_sucesso": sum(1 for r in resultados if r["status"] == "✅"),
        "contratos_erro": sum(1 for r in resultados if r["status"] != "✅"),
        "resumo": resultados,
    }
    indice_path = OUTPUT_DIR / "INDICE_GERAL.json"
    indice_path.write_text(json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8")

    # Resumo final
    console.print(
        Panel(
            "[bold green]✅ Processamento concluído![/bold green]",
            title="🏁 Resumo",
            border_style="bold green",
        )
    )

    # Tabela de resultados
    table = Table(title="📊 Resumo de Contratos Processados")
    table.add_column("Contrato", style="cyan")
    table.add_column("Contratante", style="magenta")
    table.add_column("Contratado", style="magenta")
    table.add_column("Cláusulas", justify="right")
    table.add_column("Confiança", justify="right")
    table.add_column("Problemas", justify="right", style="red")
    table.add_column("Status")

    for r in resultados:
        if r["status"] == "✅":
            table.add_row(
                r["contrato"],
                r["contratante"],
                r["contratado"],
                str(r["clausulas"]),
                r["confianca"],
                str(r["problemas"]),
                r["status"],
            )
        else:
            table.add_row(r["contrato"], "—", "—", "—", "—", "—", r["status"])

    console.print(table)

    console.print(f"\n📁 Saídas salvas em: {OUTPUT_DIR}")
    console.print(f"   ├── E1/ (cláusulas extraídas)")
    console.print(f"   ├── E2/ (estrutura JSON)")
    console.print(f"   ├── E3/ (Z3 compilation)")
    console.print(f"   ├── E4/ (análise formal)")
    console.print(f"   ├── E5/ (relatórios markdown)")
    console.print(f"   ├── MAPA_DEONTICO/ (mapeamento com rastreabilidade)")
    console.print(f"   ├── FOL/ (fórmulas em lógica de primeira ordem)")
    console.print(f"   └── INDICE_GERAL.json (resumo de todos os contratos)\n")


if __name__ == "__main__":
    processar_contratos()
