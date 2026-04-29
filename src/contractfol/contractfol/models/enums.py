"""Enumerações do domínio contratual — V3."""

from enum import Enum


class TipoDeontico(str, Enum):
    """Modalidades deônticas de Von Wright."""
    OBRIGACAO = "obrigacao"
    PROIBICAO = "proibicao"
    PERMISSAO = "permissao"
    DIREITO = "direito"
    CONDICAO = "condicao"
    PENALIDADE = "penalidade"
    DEFINICAO = "definicao"


class Severidade(str, Enum):
    """Níveis de severidade dos problemas."""
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"
    INFO = "info"


class TipoProblema(str, Enum):
    """Tipos de problemas detectáveis."""
    CONTRADICAO = "contradicao"
    INCONSISTENCIA_PRAZO = "inconsistencia_prazo"
    INCONSISTENCIA_VALOR = "inconsistencia_valor"
    LACUNA_PENALIDADE = "lacuna_penalidade"
    LACUNA_PRAZO = "lacuna_prazo"
    OBRIGACAO_SEM_RESPONSAVEL = "obrigacao_sem_responsavel"
    PROIBICAO_CONFLITA_OBRIGACAO = "proibicao_conflita_obrigacao"
    AMBIGUIDADE = "ambiguidade"
    PRAZO_IRRAZOAVEL = "prazo_irrazoavel"
