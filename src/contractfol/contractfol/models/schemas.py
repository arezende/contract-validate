"""Schemas Pydantic — Ontologia contratual V3."""

from typing import List, Optional

from pydantic import BaseModel, Field

from .enums import Severidade, TipoDeontico, TipoProblema


# ── E1: Pré-processamento ──


class Clausula(BaseModel):
    """Uma cláusula atômica extraída."""
    id: str = Field(description="Identificador único: CL_1, CL_2.1, etc.")
    numero: str = Field(description="Número da cláusula: 1, 2.1, etc.")
    texto: str = Field(description="Texto completo da cláusula")
    secao: Optional[str] = Field(default=None, description="Seção: 'DO OBJETO', 'DAS OBRIGAÇÕES', etc.")


class ContratoSegmentado(BaseModel):
    """Resultado de E1 — contrato segmentado em cláusulas."""
    arquivo: str = Field(description="Nome do arquivo")
    titulo: str = Field(description="Título/nome do contrato")
    partes: List[str] = Field(description="Partes contratantes")
    clausulas: List[Clausula] = Field(description="Cláusulas extraídas")
    texto_completo: str = Field(description="Texto integral")


# ── E2: Extração Estruturada ──


class Prazo(BaseModel):
    """Prazo com valor, unidade e referência."""
    valor: int = Field(description="Valor numérico")
    unidade: str = Field(description="dias, meses, anos")
    referencia: Optional[str] = Field(default=None, description="Referência temporal: 'após aprovação', etc.")


class Valor(BaseModel):
    """Valor monetário ou outro."""
    montante: Optional[float] = Field(default=None, description="Montante em reais")
    descricao: str = Field(description="Descrição do valor")


class ClausulaEstruturada(BaseModel):
    """Resultado de E2 — cláusula com estrutura extraída."""
    clausula_id: str = Field(description="ID: CL_2.1")
    texto_original: str = Field(description="Texto da cláusula")
    tipo_deontico: TipoDeontico = Field(description="Tipo deôntico")
    agente: str = Field(description="Agente (quem age)")
    acao: str = Field(description="Ação (o quê)")
    objeto: Optional[str] = Field(default=None, description="Objeto (sobre o quê)")
    condicao: Optional[str] = Field(default=None, description="Condição (se, quando, etc.)")
    prazo: Optional[Prazo] = Field(default=None, description="Prazo associado")
    valor: Optional[Valor] = Field(default=None, description="Valor associado")
    penalidade_ref: Optional[str] = Field(default=None, description="Referência a cláusula de penalidade")
    formula_fol: str = Field(description="Fórmula FOL em notação textual")
    codigo_z3: str = Field(description="Código Z3 executável")
    confianca: float = Field(ge=0, le=1, description="Confiança (0-1)")
    ambiguidades: List[str] = Field(default_factory=list, description="Ambiguidades detectadas")


class Extracao(BaseModel):
    """Resultado de E2 — extração completa."""
    clausulas: List[ClausulaEstruturada] = Field(description="Cláusulas estruturadas")
    mapa_deontico: dict = Field(default_factory=dict, description="Mapa de obrigações/proibições por agente")


# ── E3: Compilação Z3 ──


class FormulaCompilada(BaseModel):
    """Resultado de compilação Z3."""
    clausula_id: str
    expressao_z3: Optional[str] = None
    compilou: bool
    erro: Optional[str] = None


# ── E4: Análise Formal (6 verificações) ──


class Problema(BaseModel):
    """Um problema detectado."""
    tipo: TipoProblema = Field(description="Tipo do problema")
    severidade: Severidade = Field(description="Severidade")
    clausulas: List[str] = Field(description="Cláusulas envolvidas")
    descricao: str = Field(description="Descrição em linguagem natural")
    evidencia_formal: Optional[str] = Field(default=None, description="Evidência formal (Z3, lógica, etc.)")
    sugestao: Optional[str] = Field(default=None, description="Sugestão de correção")


class ResultadoAnalise(BaseModel):
    """Resultado de E4 — análise formal completa."""
    contrato: str = Field(description="Nome do contrato")
    total_clausulas: int = Field(description="Total de cláusulas")
    total_problemas: int = Field(description="Total de problemas detectados")
    problemas: List[Problema] = Field(default_factory=list, description="Problemas encontrados")
    mapa_deontico: dict = Field(default_factory=dict, description="Mapa por agente")
    cobertura_penalidades: float = Field(ge=0, le=1, description="% de obrigações com penalidade")
    tempo_ms: float = Field(description="Tempo de análise em ms")


# ── E5: Relatório ──


class LinhaRelatorio(BaseModel):
    """Uma linha do relatório."""
    clausula_id: str
    tipo: str
    agente: str
    status: str = Field(description="✅ ok, ⚠️ alert, 🔴 erro")
    detalhe: str


class Relatorio(BaseModel):
    """Resultado de E5 — relatório final."""
    titulo: str
    data: str
    contrato: str
    resumo: str
    linhas: List[LinhaRelatorio]
    problemas: List[Problema]
    estatisticas: dict
