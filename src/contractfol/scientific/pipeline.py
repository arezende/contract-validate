"""Scientific ContractFOL pipeline E1-E5."""

from __future__ import annotations

import json
import os
import re
import unicodedata
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from z3 import (
    And,
    Bool,
    BoolVal,
    BoolSort,
    Const,
    DeclareSort,
    Exists,
    ForAll,
    Function,
    Implies,
    Int,
    IntSort,
    Not,
    Or,
    Solver,
    sat,
    unsat,
)

from .config import (
    CONFIDENCE_THRESHOLD,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    REPORTS_DIR,
    Z3_TIMEOUT_MS,
)
from .models import (
    ClausulaSegmentada,
    CondicaoFOL,
    EntidadeContratual,
    FormulaFOL,
    FormulaZ3Compilada,
    ItemRelatorio,
    ProblemaDetectado,
    RelatorioConformidade,
    ResultadoCompilacao,
    ResultadoPreprocessamento,
    ResultadoTraducao,
    ResultadoVerificacao,
    StatusVerificacao,
    TipoDeontico,
    TipoProblema,
)
from .prompts import build_prompt_traducao
from .refinement_loop import selecionar_estrategia_refinada

console = Console()


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return text or "item"


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def _extract_text(caminho: Path) -> str:
    suffix = caminho.suffix.lower()
    if suffix == ".txt":
        return caminho.read_text(encoding="utf-8")
    if suffix == ".docx":
        from docx import Document

        doc = Document(str(caminho))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix == ".pdf":
        from PyPDF2 import PdfReader

        reader = PdfReader(str(caminho))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Formato nao suportado: {suffix}")


def _find_clause_starts(texto: str) -> list[int]:
    pattern = re.compile(
        r"(?:^|\n)\s*(?:CL[ÁA]USULA\s+[\w]+[ªº]?\s*[-–:]?|Art(?:igo)?\.?\s*\d+[ºª]?\s*[-–:]?|\d+(?:\.\d+)*\s*[-–.]?\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ]))",
        re.IGNORECASE | re.MULTILINE,
    )
    return [m.start() for m in pattern.finditer(texto)]


def segmentar_clausulas(texto: str, contrato_id: str) -> list[ClausulaSegmentada]:
    starts = _find_clause_starts(texto)
    if not starts:
        return [
            ClausulaSegmentada(
                id=f"{contrato_id}_1", numero="1", texto=texto.strip(), contrato_origem=contrato_id
            )
        ]

    clausulas: list[ClausulaSegmentada] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(texto)
        bloco = texto[start:end].strip()
        num_match = re.search(r"(\d+(?:\.\d+)*)", bloco)
        numero = num_match.group(1) if num_match else str(idx + 1)
        clausulas.append(
            ClausulaSegmentada(
                id=f"{contrato_id}_{numero}",
                numero=numero,
                texto=bloco,
                contrato_origem=contrato_id,
            )
        )
    return clausulas


def identificar_entidades(clausula: ClausulaSegmentada) -> list[EntidadeContratual]:
    texto = clausula.texto
    entidades: list[EntidadeContratual] = []

    for match in re.finditer(r"(\d+)\s*(?:dias?|meses?|anos?)", texto, re.IGNORECASE):
        entidades.append(
            EntidadeContratual(
                nome=match.group(0).strip(), tipo="prazo", texto_original=match.group(0)
            )
        )

    for match in re.finditer(r"R\$\s*[\d.,]+", texto):
        entidades.append(
            EntidadeContratual(
                nome=match.group(0).strip(), tipo="valor", texto_original=match.group(0)
            )
        )

    partes = [
        "COB",
        "CBAt",
        "Comite Olimpico",
        "Confederacao",
        "Contratante",
        "Contratado",
        "Convenente",
        "Concedente",
        "Interveniente",
    ]
    for parte in partes:
        if re.search(parte, texto, re.IGNORECASE):
            entidades.append(EntidadeContratual(nome=parte, tipo="parte", texto_original=parte))

    return entidades


def preprocessar(caminho: Path, contrato_id: str) -> ResultadoPreprocessamento:
    console.print(
        Panel(
            f"[bold]ESTAGIO 1 - Pre-processamento[/bold]\nArquivo: {caminho.name}\nContrato ID: {contrato_id}",
            title="E1",
            border_style="dim",
        )
    )
    texto = _extract_text(caminho)
    clausulas = segmentar_clausulas(texto, contrato_id)
    for clausula in clausulas:
        clausula.entidades = identificar_entidades(clausula)

    partes = sorted({e.nome for c in clausulas for e in c.entidades if e.tipo == "parte"})
    resultado = ResultadoPreprocessamento(
        contrato_id=contrato_id,
        titulo=f"Contrato {contrato_id}",
        partes=partes,
        clausulas=clausulas,
        total_clausulas=len(clausulas),
        metadata={"arquivo": str(caminho), "tamanho_chars": len(texto)},
    )
    _imprimir_validacao_e1(resultado)
    return resultado


def _imprimir_validacao_e1(res: ResultadoPreprocessamento) -> None:
    table = Table(title=f"E1 - Pre-processamento: {res.contrato_id}", show_lines=True)
    table.add_column("ID", style="bold cyan", width=12)
    table.add_column("N", width=8)
    table.add_column("Texto", width=52)
    table.add_column("Entidades", width=24)
    for clausula in res.clausulas[:15]:
        ents = ", ".join(f"{e.nome}({e.tipo})" for e in clausula.entidades[:3]) or "-"
        table.add_row(
            clausula.id,
            clausula.numero,
            clausula.texto[:80] + ("..." if len(clausula.texto) > 80 else ""),
            ents,
        )
    console.print(table)
    console.print(
        f"Partes: {', '.join(res.partes) or '-'}\nTotal de clausulas: {res.total_clausulas}"
    )


def _chamar_llm(system: str, user: str) -> str:
    if LLM_PROVIDER == "anthropic":
        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except Exception:
            return ""
    if LLM_PROVIDER == "openai":
        try:
            from openai import OpenAI

            client = OpenAI()
            response = client.chat.completions.create(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""
    if LLM_PROVIDER == "ollama":
        try:
            import ollama

            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format="json",
            )
            return response["message"]["content"]
        except Exception:
            return ""
    return ""


def _extract_agent(texto: str) -> Optional[str]:
    candidates = [
        "COB",
        "CBAt",
        "Confederacao",
        "Contratante",
        "Contratado",
        "Convenente",
        "Concedente",
        "Interveniente",
    ]
    for cand in candidates:
        if re.search(cand, texto, re.IGNORECASE):
            return cand
    return None


def _extract_action(texto: str) -> Optional[str]:
    mapa = [
        (r"repass[a-z]*.*?(recursos?|verbas?)", "RepassarRecursos"),
        (r"prestar[a-z]*.*?contas", "ApresentarPrestacaoContas"),
        (r"utiliz[a-z]*.*?recursos?.*?pessoal", "UsarRecursosParaPessoal"),
        (r"suspender[a-z]*.*?repasses?", "SuspenderRepasses"),
        (r"rescindir[a-z]*.*?convenio", "RescindirConvenio"),
        (r"selecionar[a-z]*.*?atletas", "SelecionarAtletas"),
        (r"disponibilizar[a-z]*.*?instalacoes", "DisponibilizarInstalacoes"),
        (r"fornecer[a-z]*.*?suporte", "FornecerSuporteTecnico"),
    ]
    texto_norm = _strip_accents(texto).lower()
    for padrao, nome in mapa:
        if re.search(padrao, texto_norm):
            return nome
    return None


def _extract_deadline(texto: str) -> tuple[Optional[int], Optional[str]]:
    t = _strip_accents(texto).lower()
    match = re.search(r"(ate|em ate|no prazo de)\s+(\d+)\s+dias?", t)
    if match:
        return int(match.group(2)), "le"
    match = re.search(r"apos\s+(\d+)\s+dias?", t)
    if match:
        return int(match.group(1)), "ge"
    match = re.search(r"a cada\s+(\d+)\s+dias?", t)
    if match:
        return int(match.group(1)), "eq"
    match = re.search(r"vigencia de\s+(\d+)\s+meses?", t)
    if match:
        return int(match.group(1)) * 30, "eq"
    return None, None


def _heuristic_translate(clausula: ClausulaSegmentada, estrategia: str) -> FormulaFOL:
    texto = clausula.texto
    agente = _extract_agent(texto)
    acao = _extract_action(texto)
    prazo_dias, prazo_operador = _extract_deadline(texto)

    texto_norm = texto.lower()
    if any(
        k in texto_norm
        for k in ["vedado", "proibido", "nao podera", "não poderá", "nao pode", "não pode"]
    ):
        tipo = TipoDeontico.PROIBICAO
    elif any(k in texto_norm for k in ["podera", "poderá", "facultado", "faculdade"]):
        tipo = TipoDeontico.PERMISSAO
    elif any(k in texto_norm for k in ["direito", "faz jus"]):
        tipo = TipoDeontico.DIREITO
    elif any(k in texto_norm for k in ["caso", "se ", "quando", "desde que"]):
        tipo = TipoDeontico.CONDICAO
    else:
        tipo = TipoDeontico.OBRIGACAO

    if not agente:
        agente = "Parte"
    if not acao:
        acao = _normalize(texto.split(".")[0])[:40] or "acao"

    chave = _normalize(f"{agente}_{acao}")
    antecedente = []
    consequente = [
        CondicaoFOL(predicado=tipo.value.title(), argumentos=[agente, acao], negado=False)
    ]
    if prazo_dias is not None:
        consequente.append(
            CondicaoFOL(predicado="PrazoDias", argumentos=[acao, str(prazo_dias)], negado=False)
        )

    formula_texto = f"{tipo.value.title()}({agente}, {acao}{', ' + str(prazo_dias) if prazo_dias is not None else ''})"
    codigo_z3 = _build_z3_code(tipo, agente, acao, prazo_dias, prazo_operador, chave)
    confianca = (
        0.9
        if agente != "Parte" and acao != "acao" and prazo_dias is not None
        else 0.72
        if agente != "Parte"
        else 0.58
    )
    ambiguidades = []
    if agente == "Parte":
        ambiguidades.append("agente nao identificado com precisao")
    if acao == "acao":
        ambiguidades.append("acao nao identificada com precisao")
    if prazo_dias is None and any(k in texto_norm for k in ["dia", "dias", "meses"]):
        ambiguidades.append("prazo detectado, mas nao normalizado")

    return FormulaFOL(
        clausula_id=clausula.id,
        texto_original=texto,
        tipo_deontico=tipo,
        quantificador="universal",
        antecedente=antecedente,
        consequente=consequente,
        formula_texto=formula_texto,
        formula_z3=codigo_z3,
        confianca=confianca,
        ambiguidades=ambiguidades,
        agente=agente,
        acao=acao,
        prazo_dias=prazo_dias,
        prazo_operador=prazo_operador,
        chave_semantica=chave,
    )


def _build_z3_code(
    tipo: TipoDeontico,
    agente: str,
    acao: str,
    prazo_dias: Optional[int],
    prazo_operador: Optional[str],
    chave: str,
) -> str:
    var_map = {
        TipoDeontico.OBRIGACAO: f"Obrigacao_{chave}",
        TipoDeontico.PROIBICAO: f"Proibicao_{chave}",
        TipoDeontico.PERMISSAO: f"Permissao_{chave}",
        TipoDeontico.DIREITO: f"Direito_{chave}",
        TipoDeontico.CONDICAO: f"Condicao_{chave}",
    }
    main = var_map[tipo]
    parts = [main]
    if prazo_dias is not None:
        prazo_var = f"prazo_{chave}"
        if prazo_operador == "le":
            parts.append(f"{prazo_var} <= {prazo_dias}")
        elif prazo_operador == "ge":
            parts.append(f"{prazo_var} >= {prazo_dias}")
        else:
            parts.append(f"{prazo_var} == {prazo_dias}")
    return f"And({', '.join(parts)})"


def traduzir_clausula(clausula: ClausulaSegmentada, estrategia: str = "few_shot") -> FormulaFOL:
    system, user = build_prompt_traducao(clausula.texto, estrategia=estrategia)
    resposta = _chamar_llm(system, user)
    if resposta:
        try:
            dados = json.loads(resposta)
            return _formula_from_json(clausula, dados)
        except Exception:
            pass
    return _heuristic_translate(clausula, estrategia)


def _formula_from_json(clausula: ClausulaSegmentada, dados: dict[str, Any]) -> FormulaFOL:
    antecedente = [CondicaoFOL(**item) for item in dados.get("antecedente", [])]
    consequente = [CondicaoFOL(**item) for item in dados.get("consequente", [])]
    return FormulaFOL(
        clausula_id=clausula.id,
        texto_original=clausula.texto,
        tipo_deontico=TipoDeontico(dados.get("tipo_deontico", "condicao")),
        quantificador=dados.get("quantificador", "universal"),
        antecedente=antecedente,
        consequente=consequente,
        formula_texto=dados.get("formula_fol", ""),
        formula_z3=dados.get("codigo_z3"),
        confianca=float(dados.get("confianca", 0.5)),
        ambiguidades=list(dados.get("ambiguidades", [])),
        agente=dados.get("agente"),
        acao=dados.get("acao"),
        prazo_dias=dados.get("prazo_dias"),
        prazo_operador=dados.get("prazo_operador"),
        chave_semantica=dados.get("chave_semantica"),
    )


def traduzir_contrato(
    preprocessado: ResultadoPreprocessamento, estrategia: str = "few_shot", refinar: bool = True
) -> ResultadoTraducao:
    console.print(
        Panel(
            f"[bold]ESTAGIO 2 - Traducao NL->FOL[/bold]\nContrato: {preprocessado.contrato_id}\nClausulas: {preprocessado.total_clausulas}\nEstrategia: {estrategia}\nLLM: {LLM_PROVIDER}/{LLM_MODEL}",
            title="E2",
            border_style="blue",
        )
    )
    formulas: list[FormulaFOL] = []
    for idx, clausula in enumerate(preprocessado.clausulas, start=1):
        console.print(f"[{idx}/{preprocessado.total_clausulas}] Traduzindo {clausula.id}...")
        formula = traduzir_clausula(clausula, estrategia=estrategia)
        if refinar and formula.confianca < CONFIDENCE_THRESHOLD:
            for tentativa in range(1, 1 + 2):
                estrategia_refinada = selecionar_estrategia_refinada(formula, tentativa)
                tentativa_formula = traduzir_clausula(clausula, estrategia=estrategia_refinada)
                if tentativa_formula.confianca > formula.confianca:
                    formula = tentativa_formula
                if formula.confianca >= CONFIDENCE_THRESHOLD:
                    break
        formulas.append(formula)

    total_ambiguas = sum(1 for f in formulas if f.confianca < CONFIDENCE_THRESHOLD)
    confianca_media = (
        round(sum(f.confianca for f in formulas) / len(formulas), 3) if formulas else 0.0
    )
    resultado = ResultadoTraducao(
        contrato_id=preprocessado.contrato_id,
        formulas=formulas,
        total_traduzidas=len(formulas),
        total_ambiguas=total_ambiguas,
        taxa_confianca_media=confianca_media,
    )
    _imprimir_validacao_e2(resultado)
    return resultado


def _imprimir_validacao_e2(res: ResultadoTraducao) -> None:
    table = Table(title=f"E2 - Traducao NL->FOL: {res.contrato_id}", show_lines=True)
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Tipo", width=12)
    table.add_column("Fórmula", width=44)
    table.add_column("Conf.", justify="right", width=6)
    table.add_column("Status", width=8)
    for formula in res.formulas:
        status = "OK" if formula.confianca >= CONFIDENCE_THRESHOLD else "AMB"
        table.add_row(
            formula.clausula_id,
            formula.tipo_deontico.value,
            formula.formula_texto[:60],
            f"{formula.confianca:.2f}",
            status,
        )
    console.print(table)
    console.print(
        f"Traduzidas: {res.total_traduzidas}\nAmbiguas: {res.total_ambiguas}\nConfianca media: {res.taxa_confianca_media}"
    )


class OntologiaContratual:
    def __init__(self) -> None:
        self.Parte = DeclareSort("Parte")
        self.Acao = DeclareSort("Acao")
        self.constantes: dict[str, Any] = {
            "COB": Const("COB", self.Parte),
            "Confederacao": Const("Confederacao", self.Parte),
            "CBAt": Const("CBAt", self.Parte),
            "Parte": Const("Parte", self.Parte),
        }
        self.bools: dict[str, Any] = {}
        self.ints: dict[str, Any] = {}

    def bool_var(self, name: str):
        if name not in self.bools:
            self.bools[name] = Bool(name)
        return self.bools[name]

    def int_var(self, name: str):
        if name not in self.ints:
            self.ints[name] = Int(name)
        return self.ints[name]


def compilar_formula(formula: FormulaFOL, ontologia: OntologiaContratual) -> FormulaZ3Compilada:
    try:
        chave = formula.chave_semantica or _normalize(f"{formula.agente}_{formula.acao}")
        # Ensure symbols exist in the evaluation context.
        ontologia.bool_var(f"Obrigacao_{chave}")
        ontologia.bool_var(f"Proibicao_{chave}")
        ontologia.bool_var(f"Permissao_{chave}")
        ontologia.bool_var(f"Direito_{chave}")
        ontologia.bool_var(f"Condicao_{chave}")
        if formula.prazo_dias is not None:
            ontologia.int_var(f"prazo_{chave}")
        if formula.formula_z3:
            contexto = {
                **ontologia.constantes,
                **ontologia.bools,
                **ontologia.ints,
                "And": And,
                "Or": Or,
                "Not": Not,
                "Implies": Implies,
                "ForAll": ForAll,
                "Exists": Exists,
                "BoolVal": BoolVal,
            }
            expr = eval(formula.formula_z3, {"__builtins__": {}}, contexto)
            _ = expr
        else:
            expr = _formula_expr(formula, ontologia)
            _ = expr
        return FormulaZ3Compilada(
            clausula_id=formula.clausula_id,
            codigo_z3=formula.formula_z3 or _formula_code(formula),
            sorts_usados=["Parte", "Acao"],
            funcoes_usadas=[formula.tipo_deontico.value],
            compilou_com_sucesso=True,
            chave_semantica=chave,
        )
    except Exception as e:
        return FormulaZ3Compilada(
            clausula_id=formula.clausula_id,
            codigo_z3=formula.formula_z3 or "",
            sorts_usados=[],
            funcoes_usadas=[],
            compilou_com_sucesso=False,
            erro_compilacao=str(e),
            chave_semantica=formula.chave_semantica,
        )


def _formula_code(formula: FormulaFOL) -> str:
    chave = formula.chave_semantica or _normalize(f"{formula.agente}_{formula.acao}")
    return _build_z3_code(
        formula.tipo_deontico,
        formula.agente or "Parte",
        formula.acao or "acao",
        formula.prazo_dias,
        formula.prazo_operador,
        chave,
    )


def _formula_expr(formula: FormulaFOL, ontologia: OntologiaContratual):
    chave = formula.chave_semantica or _normalize(f"{formula.agente}_{formula.acao}")
    if formula.tipo_deontico == TipoDeontico.OBRIGACAO:
        main = ontologia.bool_var(f"Obrigacao_{chave}")
    elif formula.tipo_deontico == TipoDeontico.PROIBICAO:
        main = ontologia.bool_var(f"Proibicao_{chave}")
    elif formula.tipo_deontico == TipoDeontico.PERMISSAO:
        main = ontologia.bool_var(f"Permissao_{chave}")
    elif formula.tipo_deontico == TipoDeontico.DIREITO:
        main = ontologia.bool_var(f"Direito_{chave}")
    else:
        main = ontologia.bool_var(f"Condicao_{chave}")

    pieces = [main]
    if formula.prazo_dias is not None:
        prazo = ontologia.int_var(f"prazo_{chave}")
        if formula.prazo_operador == "le":
            pieces.append(prazo <= formula.prazo_dias)
        elif formula.prazo_operador == "ge":
            pieces.append(prazo >= formula.prazo_dias)
        else:
            pieces.append(prazo == formula.prazo_dias)
    return And(*pieces) if len(pieces) > 1 else pieces[0]


def compilar_contrato(traducao: ResultadoTraducao) -> ResultadoCompilacao:
    console.print(
        Panel(
            f"[bold]ESTAGIO 3 - Compilacao FOL->Z3[/bold]\nContrato: {traducao.contrato_id}\nFórmulas: {traducao.total_traduzidas}",
            title="E3",
            border_style="green",
        )
    )
    ontologia = OntologiaContratual()
    compiladas = [compilar_formula(formula, ontologia) for formula in traducao.formulas]
    sucesso = sum(1 for item in compiladas if item.compilou_com_sucesso)
    erros = len(compiladas) - sucesso
    resultado = ResultadoCompilacao(
        contrato_id=traducao.contrato_id,
        formulas_compiladas=compiladas,
        total_compiladas=sucesso,
        total_erros=erros,
        taxa_execucao=round(sucesso / len(compiladas), 3) if compiladas else 0.0,
    )
    _imprimir_validacao_e3(resultado)
    return resultado


def _imprimir_validacao_e3(res: ResultadoCompilacao) -> None:
    table = Table(title=f"E3 - Compilacao Z3: {res.contrato_id}", show_lines=True)
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Codigo Z3", width=50)
    table.add_column("Status", width=10)
    table.add_column("Erro", width=24)
    for item in res.formulas_compiladas:
        table.add_row(
            item.clausula_id,
            item.codigo_z3[:65] + ("..." if len(item.codigo_z3) > 65 else ""),
            "OK" if item.compilou_com_sucesso else "ERRO",
            item.erro_compilacao or "-",
        )
    console.print(table)
    console.print(
        f"Compiladas: {res.total_compiladas}\nErros: {res.total_erros}\nTaxa de execucao: {res.taxa_execucao:.1%}"
    )


def _build_solver_for_compiladas(compilacao: ResultadoCompilacao):
    solver = Solver()
    solver.set("timeout", Z3_TIMEOUT_MS)
    ontologia = OntologiaContratual()
    for item in compilacao.formulas_compiladas:
        if not item.compilou_com_sucesso:
            continue
        chave = item.chave_semantica or _normalize(item.clausula_id)
        if f"Obrigacao_{chave}" in ontologia.bools or f"Proibicao_{chave}" in ontologia.bools:
            pass
        # Axioms for same key
        oblig = ontologia.bool_var(f"Obrigacao_{chave}")
        prob = ontologia.bool_var(f"Proibicao_{chave}")
        perm = ontologia.bool_var(f"Permissao_{chave}")
        for prazo_name in re.findall(r"prazo_([a-zA-Z0-9_]+)", item.codigo_z3):
            ontologia.int_var(f"prazo_{prazo_name}")
        solver.add(Implies(oblig, Not(prob)))
        solver.add(Implies(prob, Not(perm)))
        solver.add(Implies(oblig, perm))

        contexto = {
            **ontologia.bools,
            **ontologia.ints,
            "And": And,
            "Or": Or,
            "Not": Not,
            "Implies": Implies,
            "BoolVal": BoolVal,
        }
        expr = eval(item.codigo_z3, {"__builtins__": {}}, contexto)
        solver.assert_and_track(expr, Bool(f"track_{item.clausula_id}"))
    return solver


def _infer_tipo_problema(compilacao: ResultadoCompilacao, core_ids: list[str]) -> TipoProblema:
    by_key: dict[str, list[Any]] = defaultdict(list)
    for item in compilacao.formulas_compiladas:
        if item.clausula_id in core_ids:
            by_key[item.chave_semantica or _normalize(item.clausula_id)].append(item)
    for items in by_key.values():
        tipos = {
            next((f.funcoes_usadas[0] for f in [item] if f.funcoes_usadas), "") for item in items
        }
        if len(tipos) > 1:
            return TipoProblema.CONTRADICAO
        if any("prazo" in item.codigo_z3.lower() for item in items):
            return TipoProblema.INCONSISTENCIA_PRAZO
    return TipoProblema.CONTRADICAO


def verificar_consistencia_interna(compilacao: ResultadoCompilacao) -> ResultadoVerificacao:
    console.print(
        Panel(
            f"[bold]ESTAGIO 4 - Verificacao Formal[/bold]\nModo: Consistencia interna\nContrato: {compilacao.contrato_id}",
            title="E4",
            border_style="red",
        )
    )
    inicio = time.time()
    solver = _build_solver_for_compiladas(compilacao)
    resultado = solver.check()
    tempo_ms = (time.time() - inicio) * 1000
    problemas: list[ProblemaDetectado] = []
    if resultado == sat:
        status = StatusVerificacao.SAT
        consistente = True
    elif resultado == unsat:
        status = StatusVerificacao.UNSAT
        consistente = False
        core = [str(c) for c in solver.unsat_core()]
        clausulas = [cid.replace("track_", "") for cid in core]
        problemas.append(
            ProblemaDetectado(
                tipo=_infer_tipo_problema(compilacao, clausulas),
                clausulas_envolvidas=clausulas,
                descricao_tecnica=f"Conflito detectado entre: {', '.join(clausulas)}",
                unsat_core=clausulas,
                severidade="alta",
            )
        )
    else:
        status = StatusVerificacao.UNKNOWN
        consistente = False
    res = ResultadoVerificacao(
        contrato_ids=[compilacao.contrato_id],
        status=status,
        consistencia_interna=consistente,
        problemas=problemas,
        total_problemas=len(problemas),
        tempo_verificacao_ms=round(tempo_ms, 2),
    )
    _imprimir_validacao_e4(res)
    return res


def verificar_conformidade_cruzada(
    compilacao_a: ResultadoCompilacao, compilacao_b: ResultadoCompilacao
) -> ResultadoVerificacao:
    console.print(
        Panel(
            f"[bold]ESTAGIO 4 - Verificacao Formal[/bold]\nModo: Conformidade cruzada\nContrato A: {compilacao_a.contrato_id}\nContrato B: {compilacao_b.contrato_id}",
            title="E4",
            border_style="red",
        )
    )
    inicio = time.time()
    combinado = ResultadoCompilacao(
        contrato_id=f"{compilacao_a.contrato_id}_{compilacao_b.contrato_id}",
        formulas_compiladas=compilacao_a.formulas_compiladas + compilacao_b.formulas_compiladas,
        total_compiladas=compilacao_a.total_compiladas + compilacao_b.total_compiladas,
        total_erros=compilacao_a.total_erros + compilacao_b.total_erros,
        taxa_execucao=0.0,
    )
    solver = _build_solver_for_compiladas(combinado)
    resultado = solver.check()
    tempo_ms = (time.time() - inicio) * 1000
    problemas: list[ProblemaDetectado] = []
    if resultado == sat:
        status = StatusVerificacao.SAT
        consistente = True
    elif resultado == unsat:
        status = StatusVerificacao.UNSAT
        consistente = False
        core = [str(c) for c in solver.unsat_core()]
        clausulas = [cid.replace("track_", "") for cid in core]
        problemas.append(
            ProblemaDetectado(
                tipo=_infer_tipo_problema(combinado, clausulas),
                clausulas_envolvidas=clausulas,
                descricao_tecnica=f"Incompatibilidade entre contratos: {', '.join(clausulas)}",
                unsat_core=clausulas,
                severidade="alta",
            )
        )
    else:
        status = StatusVerificacao.UNKNOWN
        consistente = False
    res = ResultadoVerificacao(
        contrato_ids=[compilacao_a.contrato_id, compilacao_b.contrato_id],
        status=status,
        consistencia_interna=consistente,
        conformidade_cruzada=(status == StatusVerificacao.SAT),
        problemas=problemas,
        total_problemas=len(problemas),
        tempo_verificacao_ms=round(tempo_ms, 2),
    )
    _imprimir_validacao_e4(res)
    return res


def _imprimir_validacao_e4(res: ResultadoVerificacao) -> None:
    cor = {
        StatusVerificacao.SAT: "green",
        StatusVerificacao.UNSAT: "red",
        StatusVerificacao.UNKNOWN: "yellow",
        StatusVerificacao.ERRO: "red",
    }.get(res.status, "white")
    console.print(
        Panel(
            f"[{cor} bold]{res.status.value.upper()}[/{cor} bold]\nContratos: {', '.join(res.contrato_ids)}\nConsistencia interna: {'sim' if res.consistencia_interna else 'nao'}\nConformidade cruzada: {res.conformidade_cruzada if res.conformidade_cruzada is not None else 'N/A'}\nProblemas: {res.total_problemas}\nTempo: {res.tempo_verificacao_ms:.1f}ms",
            title="E4 - Resultado",
            border_style=cor,
        )
    )
    if res.problemas:
        table = Table(title="Problemas detectados", show_lines=True)
        table.add_column("Tipo", width=18)
        table.add_column("Clausulas", width=20)
        table.add_column("Descricao", width=42)
        table.add_column("Severidade", width=10)
        for problema in res.problemas:
            table.add_row(
                problema.tipo.value,
                ", ".join(problema.clausulas_envolvidas),
                problema.descricao_tecnica[:55],
                problema.severidade,
            )
        console.print(table)


def gerar_relatorio(
    verificacao: ResultadoVerificacao,
    traducao_a: ResultadoTraducao,
    traducao_b: Optional[ResultadoTraducao] = None,
) -> RelatorioConformidade:
    console.print(
        Panel(
            "[bold]ESTAGIO 5 - Relatorio de Conformidade[/bold]", title="E5", border_style="magenta"
        )
    )
    problemas_set = {cid for p in verificacao.problemas for cid in p.clausulas_envolvidas}
    itens: list[ItemRelatorio] = []
    formulas = traducao_a.formulas + (traducao_b.formulas if traducao_b else [])
    for formula in formulas:
        if formula.clausula_id in problemas_set:
            problema = next(
                (p for p in verificacao.problemas if formula.clausula_id in p.clausulas_envolvidas),
                None,
            )
            itens.append(
                ItemRelatorio(
                    clausula_id=formula.clausula_id,
                    status="invalida",
                    descricao_nl=f"Conflito detectado: {problema.descricao_tecnica if problema else 'indisponivel'}",
                    recomendacao="Revisar a clausula para remover a incompatibilidade.",
                    evidencia_formal=problema.tipo.value if problema else None,
                )
            )
        elif formula.confianca < CONFIDENCE_THRESHOLD:
            itens.append(
                ItemRelatorio(
                    clausula_id=formula.clausula_id,
                    status="ambigua",
                    descricao_nl=f"Clausula ambigua (conf: {formula.confianca:.0%}). Ambiguidades: {'; '.join(formula.ambiguidades) or '-'}",
                    recomendacao="Reescrever com mais precisao.",
                )
            )
        else:
            itens.append(
                ItemRelatorio(
                    clausula_id=formula.clausula_id,
                    status="valida",
                    descricao_nl="Clausula formalmente consistente.",
                )
            )

    total_validas = sum(1 for item in itens if item.status == "valida")
    total_invalidas = sum(1 for item in itens if item.status == "invalida")
    total_ambiguas = sum(1 for item in itens if item.status == "ambigua")

    if verificacao.status == StatusVerificacao.SAT:
        resumo = "A analise formal nao detectou contradicoes ou inconsistencias relevantes."
    elif verificacao.status == StatusVerificacao.UNSAT:
        resumo = f"Foram detectados {verificacao.total_problemas} problema(s) de conformidade."
    else:
        resumo = "A verificacao formal nao foi conclusiva; analise manual recomendada."

    relatorio = RelatorioConformidade(
        titulo="Relatorio de Conformidade Contratual - ContractFOL",
        contratos_analisados=verificacao.contrato_ids,
        data_analise=datetime.now().strftime("%Y-%m-%d %H:%M"),
        resumo_executivo=resumo,
        itens=itens,
        estatisticas={
            "total_clausulas": len(itens),
            "status_verificacao": verificacao.status.value,
            "tempo_ms": verificacao.tempo_verificacao_ms,
        },
        total_validas=total_validas,
        total_invalidas=total_invalidas,
        total_ambiguas=total_ambiguas,
    )
    _imprimir_validacao_e5(relatorio)
    _exportar_markdown(relatorio)
    return relatorio


def _imprimir_validacao_e5(rel: RelatorioConformidade) -> None:
    console.print(
        Panel(
            f"[bold]{rel.titulo}[/bold]\nContratos: {', '.join(rel.contratos_analisados)}\nData: {rel.data_analise}\n\n{rel.resumo_executivo}",
            title="E5 - Relatorio",
            border_style="magenta",
        )
    )
    table = Table(show_lines=True)
    table.add_column("Clausula", width=12)
    table.add_column("Status", width=10)
    table.add_column("Descricao", width=44)
    table.add_column("Recomendacao", width=24)
    for item in rel.itens:
        table.add_row(
            item.clausula_id, item.status, item.descricao_nl[:60], (item.recomendacao or "-")[:35]
        )
    console.print(table)
    console.print(
        f"Validas: {rel.total_validas} | Invalidas: {rel.total_invalidas} | Ambiguas: {rel.total_ambiguas}"
    )


def _exportar_markdown(rel: RelatorioConformidade) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = REPORTS_DIR / f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    linhas = [
        f"# {rel.titulo}",
        "",
        f"**Contratos analisados:** {', '.join(rel.contratos_analisados)}  ",
        f"**Data:** {rel.data_analise}  ",
        "",
        "## Resumo Executivo",
        "",
        rel.resumo_executivo,
        "",
        "## Resultado por Cláusula",
        "",
        "| Cláusula | Status | Descrição | Recomendação |",
        "|---|---|---|---|",
    ]
    for item in rel.itens:
        linhas.append(
            f"| {item.clausula_id} | {item.status} | {item.descricao_nl} | {item.recomendacao or '-'} |"
        )
    linhas.extend(
        [
            "",
            "## Estatísticas",
            "",
            f"- Válidas: **{rel.total_validas}**",
            f"- Inválidas: **{rel.total_invalidas}**",
            f"- Ambíguas: **{rel.total_ambiguas}**",
            f"- Tempo: **{rel.estatisticas.get('tempo_ms', 0):.0f}ms**",
        ]
    )
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    console.print(f"Relatorio exportado: {caminho}")


class ContractFOLScientificPipeline:
    def __init__(self) -> None:
        self.console = console

    def run(
        self, caminho_a: Path, caminho_b: Optional[Path] = None, estrategia: str = "few_shot"
    ) -> RelatorioConformidade:
        console.print(
            Panel(
                f"[bold]CONTRACTFOL - Pipeline Cientifico[/bold]\nContrato A: {caminho_a.name}\nContrato B: {caminho_b.name if caminho_b else 'N/A'}\nEstrategia: {estrategia}",
                title="ContractFOL",
                border_style="blue",
            )
        )
        prep_a = preprocessar(caminho_a, "A")
        prep_b = preprocessar(caminho_b, "B") if caminho_b else None
        trad_a = traduzir_contrato(prep_a, estrategia=estrategia)
        trad_b = traduzir_contrato(prep_b, estrategia=estrategia) if prep_b else None
        comp_a = compilar_contrato(trad_a)
        comp_b = compilar_contrato(trad_b) if trad_b else None
        verif_interna_a = verificar_consistencia_interna(comp_a)
        verif_final = verif_interna_a
        if comp_b:
            _ = verificar_consistencia_interna(comp_b)
            verif_final = verificar_conformidade_cruzada(comp_a, comp_b)
        return gerar_relatorio(verif_final, trad_a, trad_b)


def executar_pipeline(
    caminho_a: Path, caminho_b: Optional[Path] = None, estrategia: str = "few_shot"
) -> RelatorioConformidade:
    return ContractFOLScientificPipeline().run(caminho_a, caminho_b, estrategia)
