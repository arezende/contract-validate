"""Pydantic schemas for the scientific pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TipoDeontico(str, Enum):
    OBRIGACAO = "obrigacao"
    PROIBICAO = "proibicao"
    PERMISSAO = "permissao"
    DIREITO = "direito"
    CONDICAO = "condicao"


class StatusVerificacao(str, Enum):
    SAT = "sat"
    UNSAT = "unsat"
    UNKNOWN = "unknown"
    ERRO = "erro"


class TipoProblema(str, Enum):
    CONTRADICAO = "contradicao"
    LACUNA = "lacuna"
    INCONSISTENCIA_PRAZO = "inconsistencia_prazo"
    AMBIGUIDADE = "ambiguidade"
    CONFLITO_PENALIDADE = "conflito_penalidade"


class EntidadeContratual(BaseModel):
    nome: str
    tipo: str
    texto_original: str


class ClausulaSegmentada(BaseModel):
    id: str
    numero: str
    texto: str
    contrato_origem: str
    entidades: list[EntidadeContratual] = Field(default_factory=list)


class ResultadoPreprocessamento(BaseModel):
    contrato_id: str
    titulo: str
    partes: list[str]
    clausulas: list[ClausulaSegmentada]
    total_clausulas: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class CondicaoFOL(BaseModel):
    predicado: str
    argumentos: list[str]
    negado: bool = False


class FormulaFOL(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clausula_id: str
    texto_original: str
    tipo_deontico: TipoDeontico
    quantificador: str
    antecedente: list[CondicaoFOL] = Field(default_factory=list)
    consequente: list[CondicaoFOL] = Field(default_factory=list)
    formula_texto: str
    formula_z3: Optional[str] = None
    confianca: float = Field(ge=0, le=1)
    ambiguidades: list[str] = Field(default_factory=list)
    agente: Optional[str] = None
    acao: Optional[str] = None
    prazo_dias: Optional[int] = None
    prazo_operador: Optional[str] = None
    chave_semantica: Optional[str] = None


class ResultadoTraducao(BaseModel):
    contrato_id: str
    formulas: list[FormulaFOL]
    total_traduzidas: int
    total_ambiguas: int
    taxa_confianca_media: float


class FormulaZ3Compilada(BaseModel):
    clausula_id: str
    codigo_z3: str
    sorts_usados: list[str]
    funcoes_usadas: list[str]
    compilou_com_sucesso: bool
    erro_compilacao: Optional[str] = None
    chave_semantica: Optional[str] = None


class ResultadoCompilacao(BaseModel):
    contrato_id: str
    formulas_compiladas: list[FormulaZ3Compilada]
    total_compiladas: int
    total_erros: int
    taxa_execucao: float


class ProblemaDetectado(BaseModel):
    tipo: TipoProblema
    clausulas_envolvidas: list[str]
    descricao_tecnica: str
    contra_modelo: Optional[str] = None
    unsat_core: Optional[list[str]] = None
    severidade: str


class ResultadoVerificacao(BaseModel):
    contrato_ids: list[str]
    status: StatusVerificacao
    consistencia_interna: bool
    conformidade_cruzada: Optional[bool] = None
    problemas: list[ProblemaDetectado] = Field(default_factory=list)
    total_problemas: int
    tempo_verificacao_ms: float


class ItemRelatorio(BaseModel):
    clausula_id: str
    status: str
    descricao_nl: str
    recomendacao: Optional[str] = None
    evidencia_formal: Optional[str] = None


class RelatorioConformidade(BaseModel):
    titulo: str
    contratos_analisados: list[str]
    data_analise: str
    resumo_executivo: str
    itens: list[ItemRelatorio]
    estatisticas: dict[str, Any]
    total_validas: int
    total_invalidas: int
    total_ambiguas: int
