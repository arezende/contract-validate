"""
Interface de Linha de Comando do ContractFOL.

Uso:
    contractfol validate <arquivo>     - Valida um contrato
    contractfol validate-dir <dir>     - Valida todos os contratos em um diretório
    contractfol translate <texto>      - Traduz uma cláusula para FOL
    contractfol demo                   - Executa demonstração
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from contractfol.pipeline import ContractFOLPipeline, PipelineConfig, create_pipeline
from contractfol.models import VerificationStatus

app = typer.Typer(
    name="contractfol",
    help="ContractFOL - Validação Automatizada de Contratos usando LLMs e FOL",
)
console = Console()


@app.command()
def validate(
    file_path: str = typer.Argument(..., help="Caminho do arquivo de contrato"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key do LLM"),
    provider: str = typer.Option("openai", "--provider", "-p", help="Provedor LLM (openai/anthropic)"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="Modelo LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Modo verboso"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Arquivo de saída"),
):
    """
    Valida um contrato e detecta inconsistências.
    """
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Erro: Arquivo não encontrado: {file_path}[/red]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processando contrato...", total=None)

        pipeline = create_pipeline(
            api_key=api_key,
            provider=provider,
            model=model,
            verbose=verbose,
        )

        progress.update(task, description="Validando contrato...")
        report = pipeline.validate_file(file_path)

    # Exibir resultados
    _display_report(report)

    # Salvar output se especificado
    if output:
        output_path = Path(output)
        report_text = pipeline.get_report_text(report)
        output_path.write_text(report_text)
        console.print(f"\n[green]Relatório salvo em: {output}[/green]")

    # Exit code baseado no resultado
    if report.has_conflicts:
        raise typer.Exit(1)


@app.command("validate-dir")
def validate_directory(
    directory: str = typer.Argument(..., help="Diretório com contratos"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k"),
    provider: str = typer.Option("openai", "--provider", "-p"),
    model: str = typer.Option("gpt-4", "--model", "-m"),
    pattern: str = typer.Option("*.txt", "--pattern", help="Padrão de arquivos"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Valida todos os contratos em um diretório.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        console.print(f"[red]Erro: Diretório não encontrado: {directory}[/red]")
        raise typer.Exit(1)

    files = list(dir_path.glob(pattern))
    if not files:
        console.print(f"[yellow]Nenhum arquivo encontrado com padrão: {pattern}[/yellow]")
        raise typer.Exit(0)

    console.print(f"Encontrados {len(files)} arquivos para validar\n")

    pipeline = create_pipeline(
        api_key=api_key,
        provider=provider,
        model=model,
        verbose=verbose,
    )

    # Validar todos os arquivos juntos para detectar conflitos inter-contratuais
    report = pipeline.validate_contracts(file_paths=files)

    _display_report(report)

    if report.has_conflicts:
        raise typer.Exit(1)


@app.command()
def translate(
    clause_text: str = typer.Argument(..., help="Texto da cláusula a traduzir"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k"),
    provider: str = typer.Option("openai", "--provider", "-p"),
    model: str = typer.Option("gpt-4", "--model", "-m"),
):
    """
    Traduz uma cláusula para Lógica de Primeira Ordem.
    """
    pipeline = create_pipeline(api_key=api_key, provider=provider, model=model)

    result = pipeline.process_single_clause(clause_text)

    # Exibir resultado
    table = Table(title="Resultado da Tradução NL-FOL")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor", style="white")

    table.add_row("Texto Original", result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"])
    table.add_row("Modalidade", result["modality"] or "N/A")
    table.add_row("Confiança", f"{result['modality_confidence']:.2%}")
    table.add_row("Fórmula FOL", result["fol_formula"])
    table.add_row("Válida", "Sim" if result["fol_valid"] else "Não")
    table.add_row("Tentativas", str(result["translation_attempts"]))
    table.add_row("Predicados", ", ".join(result["predicates_used"]))

    if result["fol_errors"]:
        table.add_row("Erros", "\n".join(result["fol_errors"]))

    console.print(table)


@app.command()
def demo():
    """
    Executa demonstração do ContractFOL com exemplos.
    """
    console.print(Panel.fit(
        "[bold blue]ContractFOL - Demonstração[/bold blue]\n\n"
        "Este demo mostra o funcionamento do sistema de validação contratual.",
        title="Demo",
    ))

    # Exemplo de contrato com conflito
    contract_with_conflict = """
CONTRATO DE PATROCÍNIO ESPORTIVO

CLÁUSULA PRIMEIRA - DAS PARTES
O COMITÊ OLÍMPICO DO BRASIL, doravante denominado COB, e a empresa
PATROCINADORA S.A., doravante denominada PATROCINADOR, celebram o presente contrato.

CLÁUSULA SEGUNDA - DO OBJETO
O presente contrato tem por objeto o patrocínio de atletas olímpicos brasileiros.

CLÁUSULA TERCEIRA - DAS OBRIGAÇÕES DO PATROCINADOR
O PATROCINADOR obriga-se a realizar o pagamento das parcelas até o quinto dia útil
de cada mês, no valor de R$ 100.000,00 (cem mil reais).

CLÁUSULA QUARTA - DO USO DA MARCA
O PATROCINADOR obriga-se a exibir a marca do COB em todos os materiais promocionais
relacionados ao patrocínio.

CLÁUSULA QUINTA - RESTRIÇÕES DE USO
É vedado ao PATROCINADOR o uso da marca do COB sem autorização prévia por escrito.

CLÁUSULA SEXTA - DA VIGÊNCIA
O presente contrato tem vigência de 12 (doze) meses a partir da data de assinatura.
"""

    console.print("\n[bold]Contrato de Exemplo (com conflito intencional):[/bold]")
    console.print(Panel(contract_with_conflict[:500] + "...", title="Contrato"))

    console.print("\n[bold]Processando...[/bold]")

    # Processar sem LLM (modo heurístico)
    config = PipelineConfig(verbose=True)
    pipeline = ContractFOLPipeline(config=config)

    report = pipeline.validate_text(contract_with_conflict)

    _display_report(report)

    console.print("\n[bold green]Demonstração concluída![/bold green]")
    console.print(
        "\nNota: Para melhores resultados, configure uma API key de LLM:\n"
        "  export OPENAI_API_KEY=sua-chave\n"
        "  contractfol validate contrato.txt"
    )


@app.command()
def ontology():
    """
    Exibe a ontologia de domínio disponível.
    """
    from contractfol.ontology import get_ontology

    ont = get_ontology()

    console.print(Panel.fit(
        "[bold blue]Ontologia ContractFOL[/bold blue]\n"
        "Predicados disponíveis para formalização de contratos.",
        title="Ontologia",
    ))

    table = Table(title="Predicados")
    table.add_column("Predicado", style="cyan")
    table.add_column("Descrição", style="white")
    table.add_column("Argumentos", style="green")

    for name, pred in ont.predicates.items():
        args = ", ".join(f"{n}:{t}" for n, t in zip(pred.argument_names, pred.argument_types))
        table.add_row(pred.signature(), pred.description, args)

    console.print(table)


def _display_report(report):
    """Exibe relatório de validação."""
    # Status
    status_color = {
        VerificationStatus.SAT: "green",
        VerificationStatus.UNSAT: "red",
        VerificationStatus.UNKNOWN: "yellow",
        VerificationStatus.ERROR: "red",
    }

    color = status_color.get(report.status, "white")
    status_text = {
        VerificationStatus.SAT: "CONSISTENTE",
        VerificationStatus.UNSAT: "INCONSISTENTE",
        VerificationStatus.UNKNOWN: "INDETERMINADO",
        VerificationStatus.ERROR: "ERRO",
    }

    console.print(f"\n[bold {color}]Status: {status_text.get(report.status, report.status.value)}[/bold {color}]")

    # Estatísticas
    stats_table = Table(title="Estatísticas")
    stats_table.add_column("Métrica", style="cyan")
    stats_table.add_column("Valor", style="white")

    stats_table.add_row("Contratos", str(len(report.contract_ids)))
    stats_table.add_row("Total de cláusulas", str(report.total_clauses))
    stats_table.add_row("Cláusulas traduzidas", str(report.clauses_translated))
    stats_table.add_row("Taxa de tradução", f"{report.translation_success_rate:.1%}")
    stats_table.add_row("Conflitos detectados", str(report.conflict_count))
    stats_table.add_row("Tempo total", f"{report.total_time_ms:.1f}ms")

    console.print(stats_table)

    # Conflitos
    if report.has_conflicts:
        console.print("\n[bold red]CONFLITOS DETECTADOS:[/bold red]")

        for i, conflict in enumerate(report.conflicts, 1):
            console.print(Panel(
                f"[bold]Tipo:[/bold] {conflict.conflict_type.value}\n"
                f"[bold]Severidade:[/bold] {conflict.severity}\n"
                f"[bold]Cláusulas:[/bold] {', '.join(conflict.clause_ids)}\n\n"
                f"[bold]Explicação:[/bold]\n{conflict.explanation or 'N/A'}\n\n"
                f"[bold]Sugestão:[/bold] {conflict.suggestion or 'N/A'}",
                title=f"Conflito {i}",
                border_style="red",
            ))
    else:
        console.print("\n[bold green]Nenhum conflito detectado.[/bold green]")


def main():
    """Ponto de entrada principal."""
    app()


if __name__ == "__main__":
    main()
