#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de logging para compilações E2 -> E3 (Deontic Maps -> FOL Formulas).

Rastreia todas as compilações com:
- Timestamp
- ID do contrato
- Arquivos de entrada/saída
- Estatísticas (num cláusulas, regras, fórmulas)
- Status (sucesso/erro)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class CompilationStatus(Enum):
    """Status de uma compilação."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class CompilationEntry:
    """Registro de uma compilação."""
    timestamp: str
    contract_id: str
    status: str
    deontic_map_file: str
    fol_formula_file: str
    num_clauses: int
    num_deontic_rules: int
    num_fol_formulas: int
    compilation_time_ms: Optional[float] = None
    error: Optional[str] = None
    warning: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        data = asdict(self)
        data['status'] = self.status if isinstance(self.status, str) else self.status.value
        return data


class CompilationLogger:
    """Logger para compilações E2 -> E3."""

    def __init__(self, log_file: str = "src/contractfol/contractfol/data/output/compilation_logs.json"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Garante que o arquivo de log existe."""
        if not self.log_file.exists():
            initial_log = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "compilations": [],
                "statistics": {
                    "total": 0,
                    "successful": 0,
                    "errors": 0,
                    "total_clauses": 0,
                    "total_deontic_rules": 0,
                    "total_fol_formulas": 0
                }
            }
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(initial_log, f, ensure_ascii=False, indent=2)

    def log_compilation(self, entry: CompilationEntry) -> None:
        """
        Registra uma compilação.

        Args:
            entry: Registro da compilação
        """
        # Carregar log
        with open(self.log_file, encoding='utf-8') as f:
            log_data = json.load(f)

        # Adicionar nova compilação
        log_data["compilations"].append(entry.to_dict())

        # Atualizar estatísticas
        stats = log_data["statistics"]
        stats["total"] += 1
        stats["total_clauses"] += entry.num_clauses
        stats["total_deontic_rules"] += entry.num_deontic_rules
        stats["total_fol_formulas"] += entry.num_fol_formulas

        if entry.status == CompilationStatus.SUCCESS.value:
            stats["successful"] += 1
        elif entry.status == CompilationStatus.ERROR.value:
            stats["errors"] += 1

        log_data["last_updated"] = datetime.now().isoformat()

        # Salvar
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    def log_success(self, contract_id: str, deontic_map: Dict[str, Any],
                   fol_formula: Dict[str, Any], compilation_time_ms: float = None,
                   metadata: Dict[str, Any] = None) -> None:
        """
        Registra uma compilação bem-sucedida.

        Args:
            contract_id: ID do contrato (ex: "contrato_1")
            deontic_map: Dados do mapa deôntico
            fol_formula: Dados da fórmula FOL
            compilation_time_ms: Tempo de compilação em milissegundos
            metadata: Metadados adicionais
        """
        entry = CompilationEntry(
            timestamp=datetime.now().isoformat(),
            contract_id=contract_id,
            status=CompilationStatus.SUCCESS.value,
            deontic_map_file=f"{contract_id}_deontic_map.json",
            fol_formula_file=f"{contract_id}_fol_formula.json",
            num_clauses=len(deontic_map.get("clausulas", [])) if deontic_map else 0,
            num_deontic_rules=len(deontic_map.get("regras_deonticas", [])) if deontic_map else 0,
            num_fol_formulas=len(fol_formula.get("formulas", [])) if fol_formula else 0,
            compilation_time_ms=compilation_time_ms,
            metadata=metadata
        )
        self.log_compilation(entry)

    def log_error(self, contract_id: str, error_msg: str, deontic_map: Dict[str, Any] = None,
                  metadata: Dict[str, Any] = None) -> None:
        """
        Registra um erro de compilação.

        Args:
            contract_id: ID do contrato
            error_msg: Mensagem de erro
            deontic_map: Dados do mapa deôntico (se disponível)
            metadata: Metadados adicionais
        """
        entry = CompilationEntry(
            timestamp=datetime.now().isoformat(),
            contract_id=contract_id,
            status=CompilationStatus.ERROR.value,
            deontic_map_file=f"{contract_id}_deontic_map.json",
            fol_formula_file=f"{contract_id}_fol_formula.json",
            num_clauses=len(deontic_map.get("clausulas", [])) if deontic_map else 0,
            num_deontic_rules=len(deontic_map.get("regras_deonticas", [])) if deontic_map else 0,
            num_fol_formulas=0,
            error=error_msg,
            metadata=metadata
        )
        self.log_compilation(entry)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna as estatísticas de compilações."""
        with open(self.log_file, encoding='utf-8') as f:
            log_data = json.load(f)
        return log_data["statistics"]

    def get_compilations(self, contract_id: Optional[str] = None,
                        status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna compilações, opcionalmente filtradas.

        Args:
            contract_id: Filtro por ID do contrato
            status: Filtro por status

        Returns:
            Lista de compilações
        """
        with open(self.log_file, encoding='utf-8') as f:
            log_data = json.load(f)

        compilations = log_data["compilations"]

        if contract_id:
            compilations = [c for c in compilations if c["contract_id"] == contract_id]

        if status:
            compilations = [c for c in compilations if c["status"] == status]

        return compilations

    def print_summary(self) -> None:
        """Imprime um resumo das compilações."""
        with open(self.log_file, encoding='utf-8') as f:
            log_data = json.load(f)

        stats = log_data["statistics"]
        print("\n" + "=" * 70)
        print("RESUMO DE COMPILACOES E2 -> E3")
        print("=" * 70)
        print(f"Total de compilacoes: {stats['total']}")
        print(f"Bem-sucedidas: {stats['successful']}")
        print(f"Erros: {stats['errors']}")
        print(f"Total de clausulas: {stats['total_clauses']}")
        print(f"Total de regras deonticas: {stats['total_deontic_rules']}")
        print(f"Total de formulas FOL: {stats['total_fol_formulas']}")
        print(f"Ultima atualizacao: {log_data['last_updated']}")
        print("=" * 70 + "\n")


# Singleton global para facilitar uso
_logger_instance: Optional[CompilationLogger] = None


def get_logger() -> CompilationLogger:
    """Retorna a instância global do logger."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = CompilationLogger()
    return _logger_instance
