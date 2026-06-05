"""E2 — Extração Estruturada via LLM (JSON)."""

import json
import os
import re

from rich.console import Console
from rich.table import Table

from contractfol.contractfol.config import (
    LLM_API_KEY,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
)
from contractfol.contractfol.models import (
    Clausula,
    ClausulaEstruturada,
    ContratoSegmentado,
    Extracao,
    Prazo,
    TipoDeontico,
    Valor,
)
from contractfol.contractfol.prompts import build_prompt_extracao

console = Console()


def _chamar_llm(system: str, user: str) -> str:
    """Chama LLM (Anthropic/OpenAI/Google Gemini)."""
    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=LLM_API_KEY)
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    elif LLM_PROVIDER in ("openai", "deepseek"):
        from openai import OpenAI

        api_key = LLM_API_KEY or os.getenv("OPENAI_API_KEY") if LLM_PROVIDER == "openai" else (LLM_API_KEY or os.getenv("DEEPSEEK_API_KEY"))
        base_url = "https://api.deepseek.com" if LLM_PROVIDER == "deepseek" else None

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    elif LLM_PROVIDER == "google":
        import google.generativeai as genai

        genai.configure(api_key=LLM_API_KEY)
        model = genai.GenerativeModel(LLM_MODEL)
        response = model.generate_content(
            f"{system}\n\n{user}",
            generation_config={
                "temperature": LLM_TEMPERATURE,
                "max_output_tokens": LLM_MAX_TOKENS,
            },
        )
        return response.text

    else:
        raise ValueError(f"Provider não suportado: {LLM_PROVIDER}")


def extrair_clausula(clausula: Clausula) -> ClausulaEstruturada:
    """E2: Extrai uma cláusula em JSON estruturado."""
    system, user = build_prompt_extracao(clausula.texto)
    resposta_raw = _chamar_llm(system, user)

    # Parse JSON
    try:
        dados = json.loads(resposta_raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", resposta_raw, re.DOTALL)
        if json_match:
            try:
                dados = json.loads(json_match.group())
            except json.JSONDecodeError:
                return _clausula_erro(clausula, "JSON inválido")
        else:
            return _clausula_erro(clausula, "Sem JSON na resposta")

    # Mapear para schema
    try:
        prazo = None
        if dados.get("prazo"):
            prazo = Prazo(**dados["prazo"])

        valor = None
        if dados.get("valor"):
            valor = Valor(**dados["valor"])

        return ClausulaEstruturada(
            clausula_id=clausula.id,
            texto_original=clausula.texto,
            tipo_deontico=TipoDeontico(dados.get("tipo_deontico", "condicao")),
            agente=dados.get("agente", "—"),
            acao=dados.get("acao", "—"),
            objeto=dados.get("objeto"),
            condicao=dados.get("condicao"),
            prazo=prazo,
            valor=valor,
            penalidade_ref=dados.get("penalidade_ref"),
            formula_fol=dados.get("formula_fol", ""),
            codigo_z3=dados.get("codigo_z3", ""),
            confianca=float(dados.get("confianca", 0.5)),
            ambiguidades=dados.get("ambiguidades", []),
        )
    except Exception as e:
        return _clausula_erro(clausula, str(e))


def _clausula_erro(clausula: Clausula, erro: str) -> ClausulaEstruturada:
    """Cria ClausulaEstruturada com erro."""
    return ClausulaEstruturada(
        clausula_id=clausula.id,
        texto_original=clausula.texto,
        tipo_deontico=TipoDeontico.CONDICAO,
        agente="—",
        acao="—",
        formula_fol="ERRO",
        codigo_z3="",
        confianca=0.0,
        ambiguidades=[erro],
    )


def extrair_contrato(contrato: ContratoSegmentado) -> Extracao:
    """E2: Extrai todas as cláusulas do contrato."""
    console.print(f"\n🧠 E2 — Extração Estruturada: {len(contrato.clausulas)} cláusulas")

    clausulas_estruturadas = []
    for i, clausula in enumerate(contrato.clausulas):
        console.print(f"  [{i+1}/{len(contrato.clausulas)}] {clausula.id}...", end=" ")
        ce = extrair_clausula(clausula)
        clausulas_estruturadas.append(ce)
        console.print("✅")

    # Mapa deôntico
    mapa = {}
    tipo_plural = {
        TipoDeontico.OBRIGACAO: "obrigacoes",
        TipoDeontico.PROIBICAO: "proibicoes",
        TipoDeontico.PERMISSAO: "permissoes",
        TipoDeontico.DIREITO: "direitos",
        TipoDeontico.PENALIDADE: "penalidades",
    }

    for ce in clausulas_estruturadas:
        agente = ce.agente
        if agente not in mapa:
            mapa[agente] = {
                "obrigacoes": [],
                "proibicoes": [],
                "permissoes": [],
                "direitos": [],
                "penalidades": [],
            }
        tipo_key = tipo_plural.get(ce.tipo_deontico, None)
        if tipo_key and ce.tipo_deontico != TipoDeontico.DEFINICAO and ce.tipo_deontico != TipoDeontico.CONDICAO:
            mapa[agente][tipo_key].append(ce.clausula_id)

    resultado = Extracao(clausulas=clausulas_estruturadas, mapa_deontico=mapa)

    # Validação E2
    _imprimir_validacao_e2(resultado)
    return resultado


def _imprimir_validacao_e2(extracao: Extracao):
    """Imprime saída formatada de E2."""
    table = Table(title="✅ E2 — Extração Estruturada", show_lines=True)
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Tipo", width=12)
    table.add_column("Agente", width=15)
    table.add_column("Ação (preview)", width=30)
    table.add_column("Prazo", width=8)
    table.add_column("Conf.", width=6)

    for ce in extracao.clausulas:
        prazo_str = (
            f"{ce.prazo.valor}{ce.prazo.unidade[0]}" if ce.prazo else "—"
        )
        conf_cor = "green" if ce.confianca >= 0.7 else "yellow" if ce.confianca >= 0.4 else "red"

        table.add_row(
            ce.clausula_id,
            ce.tipo_deontico.value[:12],
            ce.agente[:15],
            ce.acao[: min(30, len(ce.acao))],
            prazo_str,
            f"[{conf_cor}]{ce.confianca:.2f}[/{conf_cor}]",
        )

    console.print(table)

    # Mapa deôntico
    console.print("\n📊 Mapa deôntico:")
    for agente, tipos in extracao.mapa_deontico.items():
        obr = len(tipos["obrigacoes"])
        prb = len(tipos["proibicoes"])
        prm = len(tipos["permissoes"])
        drtt = len(tipos["direitos"])
        pnl = len(tipos["penalidades"])
        console.print(
            f"  {agente:20} │ {obr} obrigações │ {prb} proibições │ {prm} permissões │ {pnl} penalidades"
        )

    media_conf = sum(c.confianca for c in extracao.clausulas) / len(extracao.clausulas) if extracao.clausulas else 0
    console.print(f"\n  Confiança média: {media_conf:.2f}\n")
