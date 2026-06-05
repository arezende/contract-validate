"""E1 — Pré-processamento: Extração via LLM de cláusulas e partes."""

import json
import re
from pathlib import Path
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from contractfol.contractfol.config import LLM_API_KEY, LLM_MODEL, LLM_PROVIDER, LLM_TEMPERATURE, LLM_MAX_TOKENS
from contractfol.contractfol.models import Clausula, ContratoSegmentado

console = Console()


def extrair_texto(caminho: Path) -> str:
    """Extrai texto bruto do arquivo."""
    sufixo = caminho.suffix.lower()

    if sufixo == ".txt":
        return caminho.read_text(encoding="utf-8")

    elif sufixo == ".docx":
        try:
            from docx import Document
            doc = Document(str(caminho))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise ImportError("python-docx não instalado")

    elif sufixo == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(caminho))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise ImportError("PyPDF2 não instalado")

    else:
        raise ValueError(f"Formato não suportado: {sufixo}")


def _chamar_llm_e1(texto: str) -> dict:
    """Chama LLM para extrair cláusulas e partes contratantes."""
    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=LLM_API_KEY)
    elif LLM_PROVIDER in ("openai", "deepseek"):
        from openai import OpenAI
        import os
        api_key = LLM_API_KEY or os.getenv("OPENAI_API_KEY") if LLM_PROVIDER == "openai" else (LLM_API_KEY or os.getenv("DEEPSEEK_API_KEY"))
        base_url = "https://api.deepseek.com" if LLM_PROVIDER == "deepseek" else None
        client = OpenAI(api_key=api_key, base_url=base_url)
    elif LLM_PROVIDER == "google":
        import google.generativeai as genai
        genai.configure(api_key=LLM_API_KEY)
        client = genai.GenerativeModel(LLM_MODEL)
    else:
        raise ValueError(f"Provider desconhecido: {LLM_PROVIDER}")

    system_prompt = """Você é um especialista em análise jurídica e contratual.
Sua tarefa é extrair cláusulas de um contrato e identificar as partes contratantes.

IMPORTANTE:
- Extraia TODAS as cláusulas numeradas ou seções do contrato
- Para cada cláusula, identifique: número, título/seção (se houver), texto completo
- Identifique o CONTRATANTE (quem oferece o serviço/produto ou é o primeiro signatário)
- Identifique o CONTRATADO (quem recebe o serviço/produto ou é o segundo signatário)

Responda SEMPRE em JSON válido com este formato:
{
  "clausulas": [
    {"numero": "1", "titulo": "DO OBJETO", "texto": "...completo..."},
    {"numero": "2", "titulo": "DAS OBRIGAÇÕES", "texto": "...completo..."}
  ],
  "contratante": "Nome da organização contratante",
  "contratado": "Nome da organização contratada"
}"""

    user_prompt = f"""Extraia as cláusulas e identifique as partes do seguinte contrato:

<contrato>
{texto}
</contrato>"""

    import time
    max_retries = 3
    base_delay = 5

    for attempt in range(max_retries):
        try:
            if LLM_PROVIDER == "anthropic":
                response = client.messages.create(
                    model=LLM_MODEL,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=LLM_TEMPERATURE,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                resposta_raw = response.content[0].text
            elif LLM_PROVIDER in ("openai", "deepseek"):
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=LLM_TEMPERATURE,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                )
                resposta_raw = response.choices[0].message.content
            elif LLM_PROVIDER == "google":
                # Gemini não separa system e user no conteúdo
                response = client.generate_content(
                    f"{system_prompt}\n\n{user_prompt}",
                    generation_config={
                        "temperature": LLM_TEMPERATURE,
                        "max_output_tokens": LLM_MAX_TOKENS,
                    },
                )
                resposta_raw = response.text
            else:
                raise ValueError(f"Provider não suportado: {LLM_PROVIDER}")

            # Extrair JSON
            try:
                resposta_json = json.loads(resposta_raw)
            except json.JSONDecodeError:
                # Fallback: tentar extrair JSON do meio da resposta
                match = re.search(r"\{.*\}", resposta_raw, re.DOTALL)
                if match:
                    resposta_json = json.loads(match.group(0))
                else:
                    raise ValueError("Não foi possível extrair JSON da resposta do LLM")

            return resposta_json

        except Exception as e:
            error_msg = str(e)
            if ("429" in error_msg or "Resource exhausted" in error_msg) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                console.print(f"[yellow]Aviso: Rate limit (429) no LLM em E1. Aguardando {delay}s antes da tentativa {attempt + 2}/{max_retries}...[/yellow]")
                time.sleep(delay)
                continue
                
            console.print(f"[yellow]Aviso: Erro ao chamar LLM em E1: {e}[/yellow]")
            return None


def segmentar_clausulas(texto: str) -> tuple[List[Clausula], tuple[str, str]]:
    """Extrai cláusulas via LLM e identifica contratante/contratado."""
    resultado_llm = _chamar_llm_e1(texto)

    if resultado_llm:
        try:
            clausulas = []
            for i, item in enumerate(resultado_llm.get("clausulas", []), 1):
                clausulas.append(
                    Clausula(
                        id=f"CL_{item.get('numero', str(i))}",
                        numero=item.get("numero", str(i)),
                        texto=item.get("texto", "").strip(),
                        secao=item.get("titulo"),
                    )
                )

            contratante = resultado_llm.get("contratante", "Desconhecido")
            contratado = resultado_llm.get("contratado", "Desconhecido")

            return clausulas, (contratante, contratado)

        except Exception as e:
            console.print(f"[yellow]Erro ao processar resposta do LLM: {e}. Usando fallback.[/yellow]")
            return _fallback_segmentacao(texto)
    else:
        return _fallback_segmentacao(texto)


def _fallback_segmentacao(texto: str) -> tuple[List[Clausula], tuple[str, str]]:
    """Fallback: segmentação por regex quando LLM falha."""
    padrao = re.compile(
        r"(?:^|\n)\s*"
        r"(?:"
        r"CL[ÁA]USULA\s+[\w]+[ªº]?\s*[-–:]?"
        r"|Art(?:igo)?\.?\s*\d+[ºª]?\s*[-–:]?"
        r"|\d+(?:\.\d+)*\s*[-–.]?\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])"
        r")",
        re.IGNORECASE | re.MULTILINE,
    )

    posicoes = [m.start() for m in padrao.finditer(texto)]

    if not posicoes:
        clausulas = [
            Clausula(
                id="CL_1",
                numero="1",
                texto=texto.strip(),
                secao=None,
            )
        ]
    else:
        clausulas = []
        for i, pos in enumerate(posicoes):
            fim = posicoes[i + 1] if i + 1 < len(posicoes) else len(texto)
            bloco = texto[pos:fim].strip()
            num_match = re.match(r".*?(\d+(?:\.\d+)*)", bloco)
            numero = num_match.group(1) if num_match else str(i + 1)
            secao_match = re.search(r"-\s*([A-Z\s]+?)(?:\n|$)", bloco)
            secao = secao_match.group(1).strip() if secao_match else None

            clausulas.append(
                Clausula(
                    id=f"CL_{numero}",
                    numero=numero,
                    texto=bloco,
                    secao=secao,
                )
            )

    # Fallback: extrair partes contratantes
    # Procura primeiro por "Contratante/Contratado [NOME] [TIPO]"
    match_explicit = re.search(
        r"Contratante\s+([A-ZÀ-ÿ][A-Za-zÀ-ÿ0-9\s]+?(?:Ltda\.?|S\.A\.?|Ltd\.?|Inc\.?))",
        texto,
        re.IGNORECASE
    )
    match_contratado = re.search(
        r"Contratada\s+([A-ZÀ-ÿ][A-Za-zÀ-ÿ0-9\s]+?(?:Ltda\.?|S\.A\.?|Ltd\.?|Inc\.?))",
        texto,
        re.IGNORECASE
    )

    if match_explicit and match_contratado:
        contratante = match_explicit.group(1).strip()
        contratado = match_contratado.group(1).strip()
    else:
        # Fallback: procurar por empresas com sufixo
        empresas = re.findall(
            r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ0-9\s]+?(?:Ltda\.?|S\.A\.?|Ltd\.?|Inc\.?))\b",
            texto,
        )
        empresas_uniq = []
        seen = set()
        for emp in empresas:
            emp_clean = emp.strip()
            if emp_clean.lower() not in seen and len(emp_clean) > 5 and len(emp_clean) < 100:
                empresas_uniq.append(emp_clean)
                seen.add(emp_clean.lower())

        if len(empresas_uniq) >= 2:
            contratante = empresas_uniq[0]
            contratado = empresas_uniq[1]
        elif len(empresas_uniq) == 1:
            contratante = empresas_uniq[0]
            contratado = "Desconhecido"
        else:
            contratante = "Desconhecido"
            contratado = "Desconhecido"

    return clausulas, (contratante, contratado)


def preprocessar(caminho: Path, titulo: str | None = None) -> ContratoSegmentado:
    """E1: Pipeline completo de pré-processamento via LLM."""
    console.print(
        Panel(
            f"[bold]E1 — Pré-processamento (via LLM)[/bold]\nArquivo: {caminho.name}",
            title="📄 E1",
            border_style="dim",
        )
    )

    # 1. Extrair texto
    texto = extrair_texto(caminho)
    console.print(f"  📄 Texto extraído: {len(texto)} caracteres")

    # 2. Segmentar via LLM + extrair partes
    clausulas, (contratante, contratado) = segmentar_clausulas(texto)
    console.print(f"  ✂️  Cláusulas extraídas: {len(clausulas)}")

    # 3. Partes identificadas
    partes = [contratante, contratado]
    console.print(f"  🤝 Contratante: {contratante}")
    console.print(f"  🤝 Contratado: {contratado}")

    resultado = ContratoSegmentado(
        arquivo=caminho.name,
        titulo=titulo or f"Contrato {caminho.stem}",
        partes=partes,
        clausulas=clausulas,
        texto_completo=texto,
    )

    # Validação E1
    _imprimir_validacao_e1(resultado)
    return resultado


def _imprimir_validacao_e1(res: ContratoSegmentado):
    """Imprime saída formatada de E1."""
    table = Table(title=f"✅ E1 — {res.titulo}", show_lines=True)
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Nº", width=8)
    table.add_column("Seção", width=20)
    table.add_column("Texto (preview)", width=50)

    for c in res.clausulas[:10]:
        table.add_row(
            c.id,
            c.numero,
            c.secao or "—",
            c.texto[: min(50, len(c.texto))]
            + ("..." if len(c.texto) > 50 else ""),
        )

    console.print(table)
    console.print(f"  Total: {len(res.clausulas)} cláusulas\n")
